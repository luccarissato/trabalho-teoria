#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif

#include <ctype.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <time.h>
#endif

typedef struct {
    int to;
    size_t id;
} EdgeRef;

typedef struct {
    int u;
    int v;
} Edge;

typedef struct {
    EdgeRef *items;
    size_t count;
} AdjList;

typedef struct {
    size_t vertex_count;
    size_t edge_count;
    unsigned long long seed;
    char family[128];
    char case_name[128];
    Edge *edges;
    AdjList *adjacency;
} Graph;

typedef struct {
    bool exists;
    int *path;
    size_t path_length;
    unsigned long long edge_steps;
    unsigned long long states_explored;
} Result;

static unsigned long long monotonic_nanoseconds(void) {
#ifdef _WIN32
    LARGE_INTEGER frequency;
    LARGE_INTEGER counter;
    if (!QueryPerformanceFrequency(&frequency) || !QueryPerformanceCounter(&counter)) {
        fprintf(stderr, "erro: QueryPerformanceCounter indisponivel\n");
        exit(2);
    }
    unsigned long long ticks = (unsigned long long)counter.QuadPart;
    unsigned long long ticks_per_second = (unsigned long long)frequency.QuadPart;
    return (ticks / ticks_per_second) * 1000000000ULL
        + ((ticks % ticks_per_second) * 1000000000ULL) / ticks_per_second;
#else
    struct timespec timestamp;
    if (clock_gettime(CLOCK_MONOTONIC, &timestamp) != 0) {
        fprintf(stderr, "erro: clock_gettime indisponivel\n");
        exit(2);
    }
    return (unsigned long long)timestamp.tv_sec * 1000000000ULL
        + (unsigned long long)timestamp.tv_nsec;
#endif
}

static void hold_milliseconds(unsigned long long milliseconds) {
#ifdef _WIN32
    while (milliseconds > 0) {
        DWORD chunk = milliseconds > 0xffffffffULL ? 0xffffffffUL : (DWORD)milliseconds;
        Sleep(chunk);
        milliseconds -= chunk;
    }
#else
    struct timespec duration;
    duration.tv_sec = (time_t)(milliseconds / 1000ULL);
    duration.tv_nsec = (long)((milliseconds % 1000ULL) * 1000000ULL);
    while (nanosleep(&duration, &duration) != 0 && errno == EINTR) {}
#endif
}

static void *checked_calloc(size_t count, size_t size) {
    void *memory = calloc(count == 0 ? 1 : count, size);
    if (memory == NULL) {
        fprintf(stderr, "erro: memoria insuficiente\n");
        exit(2);
    }
    return memory;
}

static char *trim(char *text) {
    while (isspace((unsigned char)*text)) {
        ++text;
    }
    if (*text == '\0') {
        return text;
    }
    char *end = text + strlen(text) - 1;
    while (end > text && isspace((unsigned char)*end)) {
        *end-- = '\0';
    }
    return text;
}

static bool parse_unsigned(const char *text, unsigned long long *value) {
    if (*text == '\0' || *text == '-') {
        return false;
    }
    errno = 0;
    char *end = NULL;
    unsigned long long parsed = strtoull(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0') {
        return false;
    }
    *value = parsed;
    return true;
}

static int compare_edges(const void *left_pointer, const void *right_pointer) {
    const Edge *left = left_pointer;
    const Edge *right = right_pointer;
    if (left->u != right->u) return left->u < right->u ? -1 : 1;
    if (left->v != right->v) return left->v < right->v ? -1 : 1;
    return 0;
}

static int compare_refs(const void *left_pointer, const void *right_pointer) {
    const EdgeRef *left = left_pointer;
    const EdgeRef *right = right_pointer;
    if (left->to != right->to) return left->to < right->to ? -1 : 1;
    if (left->id != right->id) return left->id < right->id ? -1 : 1;
    return 0;
}

static void free_graph(Graph *graph) {
    if (graph->adjacency != NULL) {
        for (size_t vertex = 0; vertex < graph->vertex_count; ++vertex) {
            free(graph->adjacency[vertex].items);
        }
    }
    free(graph->adjacency);
    free(graph->edges);
    memset(graph, 0, sizeof(*graph));
}

static bool copy_metadata(char destination[128], const char *value, const char *key) {
    if (strlen(value) >= 128) {
        fprintf(stderr, "erro: metadado %s longo demais\n", key);
        return false;
    }
    strcpy(destination, value);
    return true;
}

static bool load_graph(const char *path, Graph *graph) {
    memset(graph, 0, sizeof(*graph));
    FILE *input = fopen(path, "r");
    if (input == NULL) {
        fprintf(stderr, "erro: nao foi possivel abrir: %s\n", path);
        return false;
    }

    char buffer[512];
    if (fgets(buffer, sizeof(buffer), input) == NULL || strcmp(trim(buffer), "TC_GRAPH 1") != 0) {
        fprintf(stderr, "erro: cabecalho esperado: TC_GRAPH 1\n");
        fclose(input);
        return false;
    }

    bool has_v = false;
    bool has_e = false;
    bool has_seed = false;
    bool has_family = false;
    bool has_case = false;
    bool found_edges = false;
    unsigned long long vertices_value = 0;
    unsigned long long edges_value = 0;

    while (fgets(buffer, sizeof(buffer), input) != NULL) {
        char *line = trim(buffer);
        if (*line == '\0' || *line == '#') continue;
        if (strcmp(line, "EDGES") == 0) {
            found_edges = true;
            break;
        }
        char *separator = strchr(line, ' ');
        if (separator == NULL) {
            fprintf(stderr, "erro: metadado invalido: %s\n", line);
            fclose(input);
            return false;
        }
        *separator = '\0';
        const char *key = line;
        const char *value = trim(separator + 1);
        if (strcmp(key, "V") == 0) {
            if (has_v || !parse_unsigned(value, &vertices_value)) goto invalid_metadata;
            has_v = true;
        } else if (strcmp(key, "E") == 0) {
            if (has_e || !parse_unsigned(value, &edges_value)) goto invalid_metadata;
            has_e = true;
        } else if (strcmp(key, "SEED") == 0) {
            if (has_seed || !parse_unsigned(value, &graph->seed)) goto invalid_metadata;
            has_seed = true;
        } else if (strcmp(key, "FAMILY") == 0) {
            if (has_family || !copy_metadata(graph->family, value, key)) goto invalid_metadata;
            has_family = true;
        } else if (strcmp(key, "CASE") == 0) {
            if (has_case || !copy_metadata(graph->case_name, value, key)) goto invalid_metadata;
            has_case = true;
        } else {
            fprintf(stderr, "erro: metadado desconhecido: %s\n", key);
            fclose(input);
            return false;
        }
        continue;

invalid_metadata:
        fprintf(stderr, "erro: metadado invalido ou duplicado: %s\n", key);
        fclose(input);
        return false;
    }

    if (!found_edges || !has_v || !has_e || !has_seed || !has_family || !has_case) {
        fprintf(stderr, "erro: metadados obrigatorios ou marcador EDGES ausentes\n");
        fclose(input);
        return false;
    }
    if (vertices_value > INT32_MAX || edges_value > SIZE_MAX) {
        fprintf(stderr, "erro: V ou E excede o limite suportado\n");
        fclose(input);
        return false;
    }

    graph->vertex_count = (size_t)vertices_value;
    graph->edge_count = (size_t)edges_value;
    graph->edges = checked_calloc(graph->edge_count, sizeof(*graph->edges));

    size_t edge_index = 0;
    while (fgets(buffer, sizeof(buffer), input) != NULL) {
        char *line = trim(buffer);
        if (*line == '\0' || *line == '#') continue;
        long long u_value = -1;
        long long v_value = -1;
        char extra = '\0';
        if (sscanf(line, "%lld %lld %c", &u_value, &v_value, &extra) != 2) {
            fprintf(stderr, "erro: aresta invalida: %s\n", line);
            fclose(input);
            free_graph(graph);
            return false;
        }
        if (edge_index >= graph->edge_count || u_value < 0 || v_value < 0
            || (unsigned long long)u_value >= vertices_value
            || (unsigned long long)v_value >= vertices_value || u_value == v_value) {
            fprintf(stderr, "erro: aresta fora do contrato: %s\n", line);
            fclose(input);
            free_graph(graph);
            return false;
        }
        int u = (int)u_value;
        int v = (int)v_value;
        if (u > v) {
            int temporary = u;
            u = v;
            v = temporary;
        }
        graph->edges[edge_index++] = (Edge){u, v};
    }
    fclose(input);
    if (edge_index != graph->edge_count) {
        fprintf(stderr, "erro: quantidade de arestas difere de E\n");
        free_graph(graph);
        return false;
    }

    qsort(graph->edges, graph->edge_count, sizeof(*graph->edges), compare_edges);
    for (size_t index = 1; index < graph->edge_count; ++index) {
        if (compare_edges(&graph->edges[index - 1], &graph->edges[index]) == 0) {
            fprintf(stderr, "erro: aresta duplicada\n");
            free_graph(graph);
            return false;
        }
    }

    size_t *degrees = checked_calloc(graph->vertex_count, sizeof(*degrees));
    for (size_t id = 0; id < graph->edge_count; ++id) {
        ++degrees[(size_t)graph->edges[id].u];
        ++degrees[(size_t)graph->edges[id].v];
    }
    graph->adjacency = checked_calloc(graph->vertex_count, sizeof(*graph->adjacency));
    for (size_t vertex = 0; vertex < graph->vertex_count; ++vertex) {
        graph->adjacency[vertex].items = checked_calloc(degrees[vertex], sizeof(EdgeRef));
    }
    for (size_t id = 0; id < graph->edge_count; ++id) {
        Edge edge = graph->edges[id];
        graph->adjacency[(size_t)edge.u].items[graph->adjacency[(size_t)edge.u].count++] =
            (EdgeRef){edge.v, id};
        graph->adjacency[(size_t)edge.v].items[graph->adjacency[(size_t)edge.v].count++] =
            (EdgeRef){edge.u, id};
    }
    for (size_t vertex = 0; vertex < graph->vertex_count; ++vertex) {
        qsort(
            graph->adjacency[vertex].items,
            graph->adjacency[vertex].count,
            sizeof(EdgeRef),
            compare_refs
        );
    }
    free(degrees);
    return true;
}

static Result find_eulerian_path(const Graph *graph) {
    Result result = {0};
    size_t n = graph->vertex_count;
    size_t m = graph->edge_count;
    if (n == 0) {
        result.exists = true;
        return result;
    }
    if (m == 0) {
        result.exists = true;
        result.path = checked_calloc(1, sizeof(int));
        result.path[0] = 0;
        result.path_length = 1;
        return result;
    }

    bool *visited = checked_calloc(n, sizeof(bool));
    int *component_stack = checked_calloc(n, sizeof(int));
    size_t active_components = 0;
    for (size_t root = 0; root < n; ++root) {
        if (graph->adjacency[root].count == 0 || visited[root]) continue;
        ++active_components;
        size_t stack_size = 0;
        component_stack[stack_size++] = (int)root;
        visited[root] = true;
        while (stack_size > 0) {
            int vertex = component_stack[--stack_size];
            AdjList neighbors = graph->adjacency[(size_t)vertex];
            for (size_t index = 0; index < neighbors.count; ++index) {
                int neighbor = neighbors.items[index].to;
                if (!visited[(size_t)neighbor]) {
                    visited[(size_t)neighbor] = true;
                    component_stack[stack_size++] = neighbor;
                }
            }
        }
    }
    free(component_stack);
    free(visited);

    size_t odd_count = 0;
    int first_odd = -1;
    for (size_t vertex = 0; vertex < n; ++vertex) {
        if (graph->adjacency[vertex].count % 2 == 1) {
            if (first_odd < 0) first_odd = (int)vertex;
            ++odd_count;
        }
    }
    if (active_components != 1 || (odd_count != 0 && odd_count != 2)) {
        return result;
    }

    int start = first_odd;
    if (start < 0) {
        for (size_t vertex = 0; vertex < n; ++vertex) {
            if (graph->adjacency[vertex].count > 0) {
                start = (int)vertex;
                break;
            }
        }
    }

    bool *used = checked_calloc(m, sizeof(bool));
    size_t *cursor = checked_calloc(n, sizeof(size_t));
    int *stack = checked_calloc(m + 1, sizeof(int));
    int *reversed = checked_calloc(m + 1, sizeof(int));
    size_t stack_size = 0;
    size_t reversed_size = 0;
    stack[stack_size++] = start;
    while (stack_size > 0) {
        int vertex = stack[stack_size - 1];
        AdjList neighbors = graph->adjacency[(size_t)vertex];
        while (cursor[(size_t)vertex] < neighbors.count
            && used[neighbors.items[cursor[(size_t)vertex]].id]) {
            ++cursor[(size_t)vertex];
        }
        if (cursor[(size_t)vertex] == neighbors.count) {
            reversed[reversed_size++] = vertex;
            --stack_size;
            continue;
        }
        EdgeRef edge = neighbors.items[cursor[(size_t)vertex]++];
        if (!used[edge.id]) {
            used[edge.id] = true;
            ++result.edge_steps;
            stack[stack_size++] = edge.to;
        }
    }

    result.exists = result.edge_steps == m && reversed_size == m + 1;
    if (result.exists) {
        result.path = checked_calloc(reversed_size, sizeof(int));
        result.path_length = reversed_size;
        for (size_t index = 0; index < reversed_size; ++index) {
            result.path[index] = reversed[reversed_size - index - 1];
        }
    }
    free(reversed);
    free(stack);
    free(cursor);
    free(used);
    return result;
}

static bool hamiltonian_search(
    const Graph *graph,
    int vertex,
    bool *visited,
    int *path,
    size_t *path_length,
    unsigned long long *states_explored
) {
    ++(*states_explored);
    if (*path_length == graph->vertex_count) return true;
    AdjList neighbors = graph->adjacency[(size_t)vertex];
    for (size_t index = 0; index < neighbors.count; ++index) {
        int neighbor = neighbors.items[index].to;
        if (visited[(size_t)neighbor]) continue;
        visited[(size_t)neighbor] = true;
        path[(*path_length)++] = neighbor;
        if (hamiltonian_search(graph, neighbor, visited, path, path_length, states_explored)) {
            return true;
        }
        --(*path_length);
        visited[(size_t)neighbor] = false;
    }
    return false;
}

static Result find_hamiltonian_path(const Graph *graph) {
    Result result = {0};
    size_t n = graph->vertex_count;
    if (n == 0) return result;
    bool *visited = checked_calloc(n, sizeof(bool));
    int *path = checked_calloc(n, sizeof(int));
    for (size_t start = 0; start < n; ++start) {
        memset(visited, 0, n * sizeof(bool));
        size_t path_length = 1;
        path[0] = (int)start;
        visited[start] = true;
        if (hamiltonian_search(
                graph,
                (int)start,
                visited,
                path,
                &path_length,
                &result.states_explored
            )) {
            result.exists = true;
            result.path = path;
            result.path_length = path_length;
            free(visited);
            return result;
        }
    }
    free(path);
    free(visited);
    return result;
}

static Result run_algorithm(const Graph *graph, const char *problem) {
    return strcmp(problem, "eulerian") == 0
        ? find_eulerian_path(graph)
        : find_hamiltonian_path(graph);
}

static ptrdiff_t find_edge(const Graph *graph, int u, int v) {
    if (u > v) {
        int temporary = u;
        u = v;
        v = temporary;
    }
    size_t low = 0;
    size_t high = graph->edge_count;
    while (low < high) {
        size_t middle = low + (high - low) / 2;
        Edge edge = graph->edges[middle];
        if (edge.u == u && edge.v == v) return (ptrdiff_t)middle;
        if (edge.u < u || (edge.u == u && edge.v < v)) low = middle + 1;
        else high = middle;
    }
    return -1;
}

static bool validate_eulerian_path(const Graph *graph, const Result *result) {
    if (!result->exists) return result->path_length == 0;
    if (graph->vertex_count == 0) return result->path_length == 0;
    if (result->path_length != graph->edge_count + 1) return false;
    bool *used = checked_calloc(graph->edge_count, sizeof(bool));
    bool valid = true;
    for (size_t index = 1; index < result->path_length; ++index) {
        ptrdiff_t edge = find_edge(graph, result->path[index - 1], result->path[index]);
        if (edge < 0 || used[(size_t)edge]) {
            valid = false;
            break;
        }
        used[(size_t)edge] = true;
    }
    for (size_t id = 0; valid && id < graph->edge_count; ++id) {
        valid = used[id];
    }
    free(used);
    return valid;
}

static bool validate_hamiltonian_path(const Graph *graph, const Result *result) {
    if (!result->exists) return result->path_length == 0;
    if (result->path_length != graph->vertex_count) return false;
    bool *seen = checked_calloc(graph->vertex_count, sizeof(bool));
    bool valid = true;
    for (size_t index = 0; index < result->path_length; ++index) {
        int vertex = result->path[index];
        if (vertex < 0 || (size_t)vertex >= graph->vertex_count || seen[(size_t)vertex]) {
            valid = false;
            break;
        }
        seen[(size_t)vertex] = true;
        if (index > 0 && find_edge(graph, result->path[index - 1], vertex) < 0) {
            valid = false;
            break;
        }
    }
    free(seen);
    return valid;
}

static void print_json_string(const char *value) {
    putchar('"');
    for (const char *cursor = value; *cursor != '\0'; ++cursor) {
        if (*cursor == '\\' || *cursor == '"') putchar('\\');
        putchar(*cursor);
    }
    putchar('"');
}

static void print_result(
    const Graph *graph,
    const char *problem,
    const Result *result,
    bool valid,
    bool baseline,
    unsigned long long elapsed_nanoseconds,
    unsigned long long elapsed_total_nanoseconds,
    unsigned long long warmups,
    unsigned long long batch_size,
    unsigned long long hold_ms
) {
    printf("{\"problem\":");
    print_json_string(problem);
    printf(",\"exists\":%s,\"path\":[", result->exists ? "true" : "false");
    for (size_t index = 0; index < result->path_length; ++index) {
        if (index > 0) putchar(',');
        printf("%d", result->path[index]);
    }
    printf(
        "],\"valid\":%s,\"baseline\":%s,\"edge_steps\":%llu,"
        "\"states_explored\":%llu,",
        valid ? "true" : "false",
        baseline ? "true" : "false",
        result->edge_steps,
        result->states_explored
    );
    if (baseline) {
        printf("\"elapsed_ns\":null,\"elapsed_ns_total\":null,");
    } else {
        printf(
            "\"elapsed_ns\":%llu,\"elapsed_ns_total\":%llu,",
            elapsed_nanoseconds,
            elapsed_total_nanoseconds
        );
    }
    printf(
        "\"warmups\":%llu,\"batch_size\":%llu,\"hold_ms\":%llu,\"vertices\":%zu,"
        "\"edges\":%zu,\"seed\":%llu,\"family\":",
        warmups,
        batch_size,
        hold_ms,
        graph->vertex_count,
        graph->edge_count,
        graph->seed
    );
    print_json_string(graph->family);
    printf(",\"case\":");
    print_json_string(graph->case_name);
    printf("}\n");
}

int main(int argc, char **argv) {
    const char *problem = NULL;
    const char *input_path = NULL;
    unsigned long long warmups = 0;
    unsigned long long batch_size = 1;
    unsigned long long hold_ms = 0;
    bool baseline = false;
    for (int index = 1; index < argc; ++index) {
        if (strcmp(argv[index], "--baseline") == 0) {
            baseline = true;
            continue;
        }
        if (index + 1 >= argc) {
            fprintf(stderr, "erro: argumento sem valor\n");
            return 2;
        }
        if (strcmp(argv[index], "--problem") == 0) problem = argv[++index];
        else if (strcmp(argv[index], "--input") == 0) input_path = argv[++index];
        else if (strcmp(argv[index], "--warmups") == 0) {
            if (!parse_unsigned(argv[++index], &warmups)) {
                fprintf(stderr, "erro: warmups invalido\n");
                return 2;
            }
        }
        else if (strcmp(argv[index], "--batch-size") == 0) {
            if (!parse_unsigned(argv[++index], &batch_size) || batch_size == 0) {
                fprintf(stderr, "erro: batch-size deve ser positivo\n");
                return 2;
            }
        }
        else if (strcmp(argv[index], "--hold-ms") == 0) {
            if (!parse_unsigned(argv[++index], &hold_ms)) {
                fprintf(stderr, "erro: hold-ms invalido\n");
                return 2;
            }
        }
        else {
            fprintf(stderr, "erro: argumento desconhecido: %s\n", argv[index]);
            return 2;
        }
    }
    if (problem == NULL || input_path == NULL
        || (strcmp(problem, "eulerian") != 0 && strcmp(problem, "hamiltonian") != 0)) {
        fprintf(
            stderr,
            "erro: uso: graph_solver --problem eulerian|hamiltonian --input arquivo.graph "
            "[--warmups N] [--batch-size N] [--hold-ms N] [--baseline]\n"
        );
        return 2;
    }

    Graph graph;
    if (!load_graph(input_path, &graph)) return 2;
    Result result = {0};
    unsigned long long elapsed_total_nanoseconds = 0;
    unsigned long long elapsed_nanoseconds = 0;
    bool valid = true;
    if (!baseline) {
        for (unsigned long long repetition = 0; repetition < warmups; ++repetition) {
            Result preliminary = run_algorithm(&graph, problem);
            free(preliminary.path);
        }
        unsigned long long start = monotonic_nanoseconds();
        for (unsigned long long repetition = 0; repetition < batch_size; ++repetition) {
            Result current = run_algorithm(&graph, problem);
            if (repetition + 1 == batch_size) {
                result = current;
            } else {
                free(current.path);
            }
        }
        unsigned long long end = monotonic_nanoseconds();
        elapsed_total_nanoseconds = end - start;
        elapsed_nanoseconds = elapsed_total_nanoseconds / batch_size;
        valid = strcmp(problem, "eulerian") == 0
            ? validate_eulerian_path(&graph, &result)
            : validate_hamiltonian_path(&graph, &result);
    }
    hold_milliseconds(hold_ms);
    print_result(
        &graph,
        problem,
        &result,
        valid,
        baseline,
        elapsed_nanoseconds,
        elapsed_total_nanoseconds,
        warmups,
        batch_size,
        hold_ms
    );
    free(result.path);
    free_graph(&graph);
    return valid ? 0 : 3;
}

# Caminho Euleriano x Caminho Hamiltoniano

Projeto de Teoria da Computação que compara:

- Caminho Euleriano com o algoritmo de Hierholzer, em `Theta(V + E)`;
- Caminho Hamiltoniano com busca por backtracking, de pior caso fatorial/exponencial.

Os dois algoritmos são implementados em **C17** e **Python**, totalizando quatro combinações algoritmo-linguagem. Todas recebem os mesmos grafos e usam a mesma ordem de vizinhos.

## Estado atual

A Etapa 1 está concluída:

- formato comum de grafo e saída JSON;
- quatro implementações;
- gerador com seed fixa e manifesto SHA-256;
- validadores e oráculos independentes;
- testes cruzados entre C e Python;
- casos positivos, negativos, aleatórios e casos-limite.

Benchmarks de tempo, memória e gráficos pertencem às próximas etapas e ainda não devem ser interpretados como concluídos.

## Pré-requisitos

- Windows com PowerShell;
- GCC com suporte a C17;
- Python 3.10 ou superior, sem pacotes externos.

Ambiente validado:

```text
GCC 16.2.0
Python 3.14.10
```

## Execução manual

Compile o binário C:

```powershell
New-Item -ItemType Directory -Force .\c\bin | Out-Null
gcc -std=c17 -O2 -Wall -Wextra -Wpedantic .\c\src\main.c -o .\c\bin\graph_solver.exe
```

### C

```powershell
.\c\bin\graph_solver.exe --problem eulerian --input .\datasets\04_cycle_6.graph
.\c\bin\graph_solver.exe --problem hamiltonian --input .\datasets\07_k3_5.graph
```

### Python

```powershell
python .\python\src\main.py --problem eulerian --input .\datasets\04_cycle_6.graph
python .\python\src\main.py --problem hamiltonian --input .\datasets\07_k3_5.graph
```

Se o alias `python` do Windows não estiver funcional, confirme as instalações disponíveis com `where.exe python`.

## Formato dos grafos

```text
TC_GRAPH 1
V 3
E 2
SEED 20261117
FAMILY constructed_path
CASE positive
EDGES
0 1
1 2
```

Restrições:

- grafo simples e não direcionado;
- vértices de `0` a `V-1`;
- sem laços ou arestas duplicadas;
- exatamente `E` arestas após o marcador `EDGES`.

Cada programa imprime um objeto JSON determinístico contendo `exists`, `path`, `valid`, contadores e metadados da entrada.

## Estrutura principal

```text
c/src/main.c              Implementações e interface em C17
python/src/               Implementações e interface em Python
tools/generate.py         Gerador determinístico
tools/validate.py         Validadores independentes
datasets/                 Grafos e manifesto com hashes
relatorio.md              Relatório na ordem exigida pela disciplina
```

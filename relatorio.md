# Caminho Euleriano x Caminho Hamiltoniano

## 1. Descrição do problema e dos algoritmos

### 1.1 Escopo e modelo de entrada

O estudo compara caminhos eulerianos e hamiltonianos em grafos simples e não direcionados, com vértices de `0` a `V-1`. As implementações em C17 e Python usam as mesmas entradas e a mesma ordem de vizinhos. Os testes comparam as respostas das duas linguagens para cada problema.

O formato `TC_GRAPH 1` registra `V`, `E`, semente, família e caso, seguidos pelas arestas após `EDGES`. O leitor rejeita laços, duplicatas, vértices fora do intervalo e contagens incorretas. A saída JSON registra existência, caminho testemunha, validade, contadores, metadados e tempo.

### 1.2 Caminho euleriano e algoritmo de Hierholzer

Um caminho euleriano percorre cada aresta exatamente uma vez; vértices podem se repetir. Em um grafo não direcionado, desconsiderando vértices isolados, ele existe quando todos os vértices de grau não nulo pertencem ao mesmo componente e existem zero ou dois vértices de grau ímpar. Com dois ímpares, o caminho começa em um deles; com zero, obtém-se um circuito euleriano.

Pseudocódigo da implementação:

```text
HIERHOLZER(G):
    se V = 0: retorne o caminho vazio
    se E = 0: retorne [0]
    conte os componentes que possuem arestas
    liste os vértices de grau ímpar
    se houver mais de um componente ativo ou a quantidade de ímpares não for 0 nem 2:
        retorne inexistente
    escolha o menor vértice ímpar; se não houver, o menor vértice com aresta
    pilha <- [início]
    enquanto pilha não estiver vazia:
        v <- topo da pilha
        se v possuir aresta ainda não usada:
            marque a aresta e empilhe a outra extremidade
        senão:
            remova v da pilha e acrescente-o ao caminho invertido
    inverta o caminho
    aceite somente se exatamente E arestas foram usadas e o caminho tiver E+1 vértices
```

Cada incidência armazena um identificador de aresta, evitando que a mesma aresta não direcionada seja usada duas vezes. A ordem crescente dos vizinhos torna a testemunha determinística nas duas linguagens.

### 1.3 Caminho hamiltoniano e backtracking

Um caminho hamiltoniano visita cada vértice exatamente uma vez; não é necessário usar todas as arestas. A implementação tenta cada vértice como origem e expande recursivamente apenas vizinhos ainda não visitados. Quando uma escolha não pode ser completada, ela é desfeita.

```text
HAMILTON(G):
    para início de 0 até V-1:
        caminho <- [início]
        marque início
        se BUSCA(início): retorne caminho
    retorne inexistente

BUSCA(v):
    conte o estado explorado
    se tamanho(caminho) = V: retorne verdadeiro
    para cada vizinho u de v, em ordem crescente:
        se u não estiver marcado:
            marque u e acrescente-o ao caminho
            se BUSCA(u): retorne verdadeiro
            remova u e desmarque u
    retorne falso
```

Além da autovalidação de cada executável, os testes usam validadores externos. Para grafos pequenos, um oráculo independente verifica a condição euleriana e outro enumera caminhos hamiltonianos, sem reutilizar a implementação avaliada.

## 2. Classificação assintótica

### 2.1 Hierholzer

A análise começa com o grafo carregado. Se `E=0`, a função consulta os tamanhos do grafo e retorna imediatamente, em tempo `Theta(1)`. Nas entradas com arestas, a verificação de conectividade percorre os `V` vértices e as `2E` incidências. A contagem de graus percorre `V` listas. Quando existe caminho, a construção mantém um cursor por vértice e avança sobre cada incidência no máximo uma vez. A inversão final tem no máximo `E+1` elementos. Para `E>0`, portanto:

- limite superior: `O(V + E)`;
- limite inferior: `Omega(V + E)`, pois a rotina examina os vértices e as incidências antes de decidir se existe caminho;
- limite justo: `Theta(V + E)`.

O grafo ocupa `Theta(V + E)`. Fora da entrada, os vetores de vértices visitados e cursores ocupam `Theta(V)`. As marcas de arestas ocupam `Theta(E)), e a pilha e o caminho possuem até `E+1` posições. O espaço auxiliar no pior caso é `Theta(V + E)`. Se `E=0`, o espaço auxiliar é `Theta(1)`. O espaço total, incluindo a entrada, é `Theta(V + E)` para grafos não vazios.

### 2.2 Backtracking hamiltoniano

As chamadas recursivas visitam prefixos de permutações. Somando `V!/(V-k)!` para todos os comprimentos `k`, obtém-se `O(V!)` estados. Cada chamada examina até `V-1` vizinhos, e limpar as marcas para todos os vértices iniciais custa `O(V²)`. O pior caso geral tem limite superior `O(V × V!)`.

Nos bipartidos completos `K(a,b)` da campanha, `V=a+b` e `b-a` é 2 ou 3. A alternância entre as partes impede um caminho hamiltoniano, então a busca esgota os prefixos. Só os de comprimento `2a+1` que começam na parte maior somam `a! × b!/(b-a-1)!`, ou `Omega(a! × b!)`. Intercalando as sequências possíveis das duas partes, com até duas escolhas de início, obtém-se o teto de `2e² × a! × b!`. Cada um dos `Theta(a! × b!)` estados examina `Theta(V)` vizinhos, dando tempo `Theta(V × a! × b!)` nessa família. O contador `states_explored` registra os estados visitados.

O caminho, as marcas e a pilha recursiva usam `Theta(V)` de espaço auxiliar. Com o grafo, o espaço total é `Theta(V + E)`.

## 3. Melhor caso, pior caso e caso médio

### 3.1 Hierholzer

O melhor caso é `Theta(1)` e ocorre quando o grafo carregado não tem arestas. Para `E>0`, a varredura da representação dá tempo `Theta(V + E)` tanto nos casos aceitos quanto nos rejeitados. Assim, o pior caso tem esse limite, que também vale como caso médio para distribuições condicionadas a `E>0`. Ciclos e caminhos construídos exercitam casos positivos. Estrelas com mais de dois graus ímpares e componentes separados exercitam rejeições. A suíte de corretude cobre o retorno antecipado com os grafos vazio e unitário.

Na suíte de ciclos, `V` e `E` cresceram juntos de 1.000 para 32.000. A razão `T/(V+E)` permaneceu entre 10,38 e 18,59 ns em C e entre 477,82 e 539,02 ns em Python. As inclinações da regressão log-log foram 1,1718 e 0,9726, respectivamente, compatíveis com crescimento aproximadamente linear dentro da faixa medida. Isso confronta a previsão `Theta(V+E)` sem tratar a regressão como substituta da prova.

### 3.2 Backtracking hamiltoniano

- **Melhor caso.** Para `V>0`, a inicialização das marcas já custa `Omega(V)`. No caminho construído e ordenado, a primeira tentativa encontra a testemunha em `V` estados e examina no máximo dois vizinhos por estado. O tempo do melhor caso é, portanto, `Theta(V)`.
- **Pior caso.** Uma entrada com grande ramificação e sem solução força a exploração de muitos prefixos. Os bipartidos desbalanceados `K(a,b)` com diferença de 2 ou 3 entre as partes exercitam esse comportamento e têm o limite justo demonstrado no item 2.
- **Caso médio.** Depende da distribuição dos grafos, da densidade e da ordem dos vizinhos. A campanha usou uma instância `G(n,0,5)` por tamanho, com semente determinada, e separou o tempo e `states_explored` por família. As repetições de tempo medem a variabilidade da execução da mesma instância.

Os casos forçados confirmaram a diferença entre famílias. Nos caminhos construídos, `states_explored = V`, de 8 a 25. Nos bipartidos desbalanceados, o contador passou de 2.288 estados em `V=8` para 1.924.032 em `V=12` e 92.353.646 em `V=14`. Já os grafos `G(n,0,5)` foram não monotônicos: 620 estados em `V=13`, mas apenas 25 em `V=25`, porque a instância maior encontrou cedo uma testemunha na ordem determinística. Portanto, os dados aleatórios descrevem somente a distribuição e as sementes declaradas, não um caso médio universal.

## 4. Aplicabilidade prática

Caminhos eulerianos modelam tarefas que precisam processar conexões uma única vez, como inspeção de ruas, planejamento de rotas sobre trechos e reconstrução de sequências a partir de sobreposições. Hierholzer é adequado mesmo para grafos grandes, pois cresce linearmente com a representação.

Caminhos hamiltonianos modelam visitas únicas a locais ou estados e aparecem como subestrutura em problemas de roteamento e sequenciamento. O backtracking exato é apropriado para instâncias pequenas, ensino, validação de heurísticas e casos com poda suficiente. Para grafos grandes, seu crescimento torna necessários algoritmos especializados, programação dinâmica, solvers ou heurísticas, conforme o objetivo.

Os dois problemas ilustram que pequenas mudanças no requisito - usar cada aresta uma vez ou visitar cada vértice uma vez - podem alterar profundamente a tratabilidade computacional.

## 5. Simulação com dados reais ou sintéticos

### 5.1 Entradas congeladas

O gerador `tools/generate_experiments.py`, com semente base `20261117`, produziu 29 grafos registrados em `datasets/experimental-manifest.json`, que contém o SHA-256 do gerador e de cada entrada. A suíte pareada possui 18 grafos, com seis tamanhos por família:

- caminho construído favorável: `8, 10, 13, 16, 20, 25`;
- `G(n,0,5)` aleatório: `8, 10, 13, 16, 20, 25`;
- bipartido completo desbalanceado desfavorável: `4, 5, 6, 8, 10, 12`.

As quatro combinações algoritmo-linguagem receberam exatamente os mesmos 18 arquivos. O piloto usou a família bipartida em `V = 8, 10, 12, 14, 16`. A suíte suplementar de Hierholzer usou ciclos com `V = E = 1.000, 2.000, 4.000, 8.000, 16.000, 32.000`; ela não foi apresentada como comparação direta com Hamilton.

### 5.2 Protocolo executado

Cada ponto da campanha teve 20 repetições válidas, com três rodadas de aquecimento por repetição e JIT desativado. Chamadas rápidas foram agrupadas em lotes calibrados. O CSV bruto guarda os tempos do lote e por chamada, os contadores e os metadados da execução.

O cronômetro cobre apenas a execução do algoritmo, excluindo a leitura da entrada, a validação da resposta e a gravação da saída. C usa `QueryPerformanceCounter` no Windows e `clock_gettime(CLOCK_MONOTONIC)` em Linux/WSL. Python usa `time.perf_counter_ns()`. Execuções interrompidas pelo limite de 60 s ficam registradas como dados censurados.

A campanha registrou 1.440 observações pareadas e 240 de Hierholzer, todas válidas. No piloto, `V=14` foi o maior caso difícil concluído, em 1,669 s em C e 49,173 s em Python. Ambas as linguagens atingiram o timeout em `V=16`.

### 5.3 Memória e regra de exclusão

A memória foi medida separadamente no Windows com `PeakWorkingSet64` e `PeakPagedMemorySize64`. Cada ponto usou 15 processos novos para o baseline, que carrega o grafo, e 15 para o algoritmo. O resumo traz média, mediana, desvio-padrão amostral e o incremento aproximado `max(0, mediana_algoritmo - mediana_baseline)`. O pico inclui o grafo, as bibliotecas e, em Python, o interpretador.

Foram registradas 720 medições pareadas e 360 de Hierholzer. A análise usa tempos válidos e picos disponíveis de execuções concluídas dentro do limite. Todos os outliers válidos foram mantidos. Os dados, resumos e hashes estão em `results/raw/`, `results/summary/` e `results/analysis-manifest.json`.

## 6. Gráficos e tabelas de comparação

### 6.1 Teórico x medido

O gráfico `results/charts/euler_time_loglog.svg` mostra as duas linguagens contra `V+E`; `results/charts/euler_ratio.svg` mostra `T/(V+E)`. A relativa estabilidade da razão e as inclinações próximas de 1 sustentam empiricamente a tendência linear de Hierholzer. A tabela abaixo apresenta os extremos da suíte; cada valor é média de 20 repetições.

| Linguagem | V = E | Média | Desvio-padrão | T/(V+E) |
|---|---:|---:|---:|---:|
| C | 1.000 | 20.751 ns | 2.020 ns | 10,38 ns |
| C | 32.000 | 1.189.560 ns | 273.066 ns | 18,59 ns |
| Python | 1.000 | 1.078.036 ns | 239.183 ns | 539,02 ns |
| Python | 32.000 | 30.923.825 ns | 3.223.841 ns | 483,18 ns |

![Tempo de Hierholzer em escala log-log](results/charts/euler_time_loglog.svg)

![Razão entre tempo de Hierholzer e V mais E](results/charts/euler_ratio.svg)

Para Hamilton, `results/charts/hamilton_states.svg` e `results/charts/hamilton_time.svg` separam as famílias. No caso desfavorável, estados e tempo cresceram rapidamente:

| Linguagem | V | Estados | Média | Desvio-padrão |
|---|---:|---:|---:|---:|
| C | 8 | 2.288 | 0,026 ms | 0,002 ms |
| C | 10 | 54.970 | 0,880 ms | 0,058 ms |
| C | 12 | 1.924.032 | 34,000 ms | 3,139 ms |
| Python | 8 | 2.288 | 0,910 ms | 0,096 ms |
| Python | 10 | 54.970 | 24,997 ms | 1,250 ms |
| Python | 12 | 1.924.032 | 1.122,373 ms | 435,931 ms |

![Tempo do backtracking hamiltoniano por família](results/charts/hamilton_time.svg)

![Estados explorados pelo backtracking](results/charts/hamilton_states.svg)

Para confrontar o modelo teórico com as medições, o gráfico a seguir divide o tempo médio por `f(V)=V × a! × b!`, o limite justo obtido no item 2 para a família bipartida. Entre `V=8` e `V=12`, a razão varia de 4,55 a 5,09 em C e de 144,66 a 157,93 em Python, em nanossegundos por unidade de `f(V)`. A relativa estabilidade nesse intervalo é compatível com o modelo. As instâncias menores exibem mais variação, em especial `V=5`, cuja diferença entre as partes é 3. Na família aleatória, o número de estados depende de quando a ordem de vizinhos encontra uma testemunha, o que explica a curva não monotônica.

![Razão entre o tempo medido e o modelo fatorial da família bipartida](results/charts/hamilton_ratio.svg)

O gráfico do piloto mostra as execuções individuais até `V=14` e marca `V=16` com um triângulo no limite de 60 s para as duas linguagens. O triângulo indica censura pelo limite externo. Em `V=14`, os tempos observados foram 1,669 s em C e 49,173 s em Python.

![Viabilidade do backtracking e ponto de timeout nas duas linguagens](results/charts/hamilton_viability.svg)

### 6.2 Algoritmo x algoritmo e C x Python

`results/charts/paired_algorithms.svg` compara os algoritmos somente nos mesmos caminhos construídos. Em `V=25`, C mediu 918 ns para Euler e 351 ns para Hamilton; Python mediu 24.304 ns e 15.287 ns. O backtracking favorável pode ser mais rápido nesse intervalo porque segue imediatamente uma sequência de `V` estados, apesar de possuir pior caso muito superior. O contraste com a família bipartida mostra por que uma medição apenas favorável seria enganosa.

`results/charts/language_ratio.svg` usa a razão C/Python. Em `V=25`, ela foi 0,0378 para Euler e 0,0230 para Hamilton, equivalentes a Python aproximadamente 26 e 44 vezes mais lento nessas instâncias. A diferença é de constante e representação; não altera as classes assintóticas.

| Entrada pareada | Algoritmo | Média em C | Média em Python |
|---|---|---:|---:|
| Caminho, V=25 | Hierholzer | 918 ns | 24.304 ns |
| Caminho, V=25 | Backtracking | 351 ns | 15.287 ns |
| Bipartido desbalanceado, V=12 | Hierholzer | 214 ns | 6.997 ns |
| Bipartido desbalanceado, V=12 | Backtracking | 34,000 ms | 1.122,373 ms |

![Comparação entre Euler e Hamilton em entradas pareadas](results/charts/paired_algorithms.svg)

![Razão de tempo entre C e Python](results/charts/language_ratio.svg)

### 6.3 Memória

`results/charts/memory_peak.svg` apresenta o pico absoluto e `results/charts/memory_increment.svg` o incremento aproximado sobre o baseline. Nos ciclos, o pico médio de C cresceu de 4.001.246 bytes em `V=1.000` para 6.887.014 em `V=32.000`; Python cresceu de 18.788.352 para 39.030.238 bytes. A tendência é coerente com espaço total `Theta(V+E)` e evidencia o custo maior de objetos e do interpretador Python.

O incremento é mais ruidoso e às vezes zero porque é a diferença entre medianas de processos distintos, arredondada pela granularidade do working set. Por isso, ele é diagnóstico complementar, não prova isolada de espaço auxiliar. Médias, medianas, desvios, mínimos e máximos completos estão em `results/summary/timing.csv` e `results/summary/memory.csv`.

![Pico absoluto de memória](results/charts/memory_peak.svg)

![Incremento aproximado de memória sobre o baseline](results/charts/memory_increment.svg)

## 7. Reflexão sobre P e NP

O problema de decisão do **Caminho Euleriano pertence a P**. Em um grafo não direcionado, verifica-se se os vértices de grau não nulo estão conectados e se há zero ou dois vértices de grau ímpar. Essas condições decidem a existência de um caminho em `O(V+E)`. Quando existe, Hierholzer também o constrói nesse limite.

O **Caminho Hamiltoniano pertence a NP**. Um certificado é uma sequência de `V` vértices. Em tempo polinomial, o verificador confere se cada vértice aparece uma única vez e se cada par consecutivo é ligado por uma aresta.

O problema é **NP-completo** por uma redução polinomial a partir de Ciclo Hamiltoniano. Substitui-se um vértice `v` por duas cópias com a mesma vizinhança e liga-se uma folha distinta a cada cópia. As folhas forçam as duas extremidades de qualquer caminho hamiltoniano no grafo transformado. Remover as folhas e reunir as cópias recupera um ciclo hamiltoniano no grafo original. No outro sentido, abrir o ciclo em `v`, separar suas extremidades entre as duas cópias e acrescentar as folhas produz um caminho hamiltoniano.

O contraste decorre de como cada problema usa o grafo. Grau e conectividade caracterizam a existência do caminho euleriano. No problema hamiltoniano, visitar cada vértice uma única vez impõe uma ordem global. Uma escolha local pode bloquear todas as continuações, então o backtracking precisa desfazê-la e explorar alternativas. A programação dinâmica por subconjuntos resolve o problema em `O(V² × 2^V)`, um custo ainda exponencial. Uma heurística pode fornecer um caminho válido quando o encontra. Uma tentativa sem sucesso deixa a existência do caminho em aberto.

Nas medições, Hierholzer chegou a `V=32.000`. No piloto da família bipartida desbalanceada, o backtracking concluiu em `V=14` e atingiu o limite de 60 s em `V=16` nas duas linguagens. Os resultados ilustram a diferença de crescimento prevista pela análise.

## Ambiente de execução

O manifesto experimental gerado com a campanha registra timestamp, commit, estado da árvore versionada, CPU, RAM, Windows, modo de energia, PowerShell, executáveis, versões e timers. O ambiente possui Intel Core i7-7700HQ, 17.033.236.480 bytes de RAM e Windows NT build 26200 em modo Equilibrado. C17 foi compilado com GCC 16.2.0 e flags `-std=c17 -O2 -Wall -Wextra -Wpedantic`; Python 3.14.10 usou CPython com JIT experimental desativado.

## Participantes e contribuições

| Integrante | Responsabilidade no projeto |
| --- | --- |
| Lucca Rissato | **Item 1.** Descrição dos problemas, pseudocódigos, implementações em C17 e Python e testes de corretude. |
| Marco Aurelio | **Itens 2 e 3.** Justificativa dos limites O, Ω e Θ e análise do melhor caso, do pior caso e do caso médio. |
| Luiz Gonzaga | **Itens 4 e 5.** Aplicações práticas, geração das entradas e execução das medições de tempo e memória, com registro do ambiente. |
| Bernardo Guimarães | **Item 6.** Produção dos gráficos e tabelas e interpretação das comparações entre teoria e medições, algoritmos e linguagens. |
| Igor Gabriel | **Item 7.** Classificação dos problemas em P e NP, redução a partir do Ciclo Hamiltoniano e discussão sobre tratabilidade. |

## Declaração de uso de IA

Foi utilizado OpenAI Codex como apoio no planejamento, criação e refatoração das implementações para C17 e Python, elaboração dos testes automatizados, instrumentação de tempo e memória, geração dos datasets, execução assistida da campanha, criação dos gráficos SVG, análise estatística e redação preliminar deste relatório.

## Referências

1. BONDY, J. A.; MURTY, U. S. R. *Graph Theory*. Springer, 2008.
2. CORMEN, T. H. et al. *Introduction to Algorithms*. 4. ed. MIT Press, 2022.
3. GAREY, M. R.; JOHNSON, D. S. *Computers and Intractability: A Guide to the Theory of NP-Completeness*. W. H. Freeman, 1979.
4. KARP, R. M. Reducibility among combinatorial problems. In: MILLER, R. E.; THATCHER, J. W. (org.). *Complexity of Computer Computations*. Plenum Press, 1972. p. 85-103.
5. MICROSOFT. *Process.PeakWorkingSet64 Property*. Microsoft Learn.
6. PYTHON SOFTWARE FOUNDATION. *time - Time access and conversions*. Python 3 documentation.

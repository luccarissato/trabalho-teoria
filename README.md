# Caminho Euleriano x Caminho Hamiltoniano

Projeto de Teoria da Computação que compara:

- Caminho Euleriano com o algoritmo de Hierholzer, em `Theta(V + E)`;
- Caminho Hamiltoniano com busca por backtracking, de pior caso fatorial/exponencial.

Os dois algoritmos são implementados em **C17** e **Python**, totalizando quatro combinações algoritmo-linguagem. Todas recebem os mesmos grafos e usam a mesma ordem de vizinhos.

## Estado atual

As Etapas 1, 2 e 3 estão concluídas:

- formato comum de grafo e saída JSON;
- quatro implementações;
- gerador com seed fixa e manifesto SHA-256;
- validadores e oráculos independentes;
- testes cruzados entre C e Python;
- casos positivos, negativos, aleatórios e casos-limite;
- cronômetros envolvendo somente a chamada do algoritmo;
- três rodadas preliminares e lotes automáticos para operações rápidas;
- 20 repetições de tempo com timeout externo de 60 segundos;
- medição de pico de memória por processo novo, com baseline e 15 repetições;
- manifesto reproduzível do ambiente de execução;
- 29 datasets experimentais congelados por SHA-256;
- 20 repetições válidas em cada ponto final de tempo;
- campanha de memória com 15 processos por modo e ponto;
- tabelas estatísticas e oito gráficos SVG regeneráveis.

O piloto registrou `V=14` como o maior caso bipartido difícil concluído em até 60 segundos nas duas linguagens e `V=16` como o primeiro ponto censurado. A reflexão formal sobre P e NP e o fechamento da entrega pertencem à Etapa 4.

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

## Medição experimental

Compile o executável C antes das medições e execute, a partir da raiz:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run-benchmarks.ps1
powershell -ExecutionPolicy Bypass -File .\tools\measure-memory.ps1
```

O primeiro comando grava as medições de tempo em `results/raw/timing.csv` e o ambiente em `results/manifest.json`. O segundo grava cada processo em `results/raw/memory.csv` e as estatísticas de memória em `results/summary/memory.csv`.

Por padrão, cada ponto de tempo usa 3 rodadas preliminares não contabilizadas, 20 repetições e timeout de 60 segundos. Operações rápidas são executadas em lotes calibrados; `elapsed_ns_total` preserva o tempo bruto do lote e `elapsed_ns` representa o tempo por chamada. A memória é coletada separadamente em 15 processos novos para o baseline e 15 para o algoritmo.

Exemplo limitado a um dataset:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run-benchmarks.ps1 -Datasets datasets\04_cycle_6.graph
powershell -ExecutionPolicy Bypass -File .\tools\measure-memory.ps1 -Datasets datasets\04_cycle_6.graph
```

## Reprodução da campanha final

Para regenerar os datasets, recompilar, executar piloto, tempos, memória, tabelas e gráficos:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run-experiments.ps1
```

Na máquina registrada em `results/manifest.json`, a campanha completa leva aproximadamente 15 minutos. Os artefatos ficam organizados assim:

```text
datasets/experimental-manifest.json  hashes e tamanhos congelados
results/raw/                         todas as observações individuais
results/summary/timing.csv           média, mediana, desvio, mínimo e máximo
results/summary/memory.csv           pico, baseline e incremento aproximado
results/summary/viability.csv        maior V concluído e primeiro timeout
results/summary/summary.txt          tabelas compactas para conferência
results/charts/                      oito gráficos SVG
results/analysis-manifest.json       hashes das entradas e saídas da análise
```

Nenhum outlier válido é removido. Somente linhas concluídas, válidas e não censuradas entram nas estatísticas; timeouts permanecem nos CSVs brutos.

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
tools/run-benchmarks.ps1  Coleta reprodutível de tempo
tools/measure-memory.ps1  Coleta de pico de memória no Windows
tools/run-experiments.ps1 Campanha experimental completa
tools/analyze.py          Estatísticas, tabelas e gráficos SVG
datasets/                 Grafos e manifesto com hashes
results/                  CSVs e manifesto experimental
relatorio.md              Relatório na ordem exigida pela disciplina
```

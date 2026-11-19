# Caminho Euleriano x Caminho Hamiltoniano

Projeto de Teoria da Computação que compara o algoritmo de Hierholzer para Caminho Euleriano, em `Theta(V + E)`, com uma busca exata por backtracking para Caminho Hamiltoniano, de pior caso fatorial/exponencial. Ambos foram implementados em **C17** e **Python**, recebem os mesmos grafos e preservam a mesma ordem de vizinhos.

## Estado atual

A parte técnica das quatro etapas está implementada:

- quatro combinações algoritmo-linguagem e validadores independentes;
- testes cruzados, casos positivos, negativos, aleatórios e casos-limite;
- 29 datasets determinísticos congelados por SHA-256;
- 20 repetições válidas de tempo por ponto final e timeout de 60 segundos;
- pico de memória medido em 15 processos novos por modo e ponto;
- tabelas estatísticas, oito gráficos SVG e manifestos de rastreabilidade;
- reprodução rápida e integral por um único script.

No piloto, `V=14` foi o maior caso bipartido difícil concluído pelas duas linguagens em até 60 segundos; `V=16` foi o primeiro ponto censurado. Antes da entrega, o grupo ainda deve preencher em `relatorio.md` os nomes e as contribuições reais, exportar o relatório como um único PDF e preparar a apresentação de até sete minutos.

## Pré-requisitos

- Windows 10 ou 11 com Windows PowerShell 5.1 ou PowerShell 7;
- GCC com suporte a C17;
- Python 3.10 ou superior, sem pacotes externos;
- Git, usado para registrar o commit nos manifestos.

Ambiente da campanha incluída no repositório:

```text
GCC 16.2.0
Python 3.14.10 (CPython, JIT experimental desativado)
Windows NT build 26200
```

Confirme as ferramentas:

```powershell
python --version
gcc --version
git --version
```

## Validação e reprodução

Execute os comandos a partir da raiz do projeto.

### Validação rápida

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run-all.ps1 -Quick
```

O modo `-Quick` compila C17 com avisos, executa os testes de corretude, regenera os 29 datasets em uma pasta temporária, faz amostras curtas de tempo e memória, regenera a análise a partir dos CSVs finais e compara os hashes das tabelas e dos oito gráficos. Duração típica: menos de dois minutos.

### Reprodução integral

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run-all.ps1 -Full
```

O modo `-Full` remove de forma controlada somente os datasets experimentais e resultados gerados, recompila, testa e refaz piloto, medições, análise, gráficos e manifestos. Ele não apaga código-fonte, documentação nem os datasets básicos da Etapa 1. Na máquina registrada em `results/manifest.json`, a campanha leva aproximadamente 15 minutos e inclui dois timeouts planejados de 60 segundos em `V=16`.

Para executar somente a campanha experimental, sem a limpeza e a auditoria final:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run-experiments.ps1
```

## Execução manual

Compile o programa C:

```powershell
New-Item -ItemType Directory -Force .\c\bin | Out-Null
gcc -std=c17 -O2 -Wall -Wextra -Wpedantic .\c\src\main.c -o .\c\bin\graph_solver.exe
```

Execute qualquer combinação:

```powershell
.\c\bin\graph_solver.exe --problem eulerian --input .\datasets\04_cycle_6.graph
.\c\bin\graph_solver.exe --problem hamiltonian --input .\datasets\07_k3_5.graph
python .\python\src\main.py --problem eulerian --input .\datasets\04_cycle_6.graph
python .\python\src\main.py --problem hamiltonian --input .\datasets\07_k3_5.graph
```

Cada programa imprime um JSON determinístico com `exists`, `path`, `valid`, contadores e metadados da entrada. Para repetir somente os testes de corretude:

```powershell
python .\tests\correctness.py --c .\c\bin\graph_solver.exe
```

## Protocolo experimental

O cronômetro envolve somente a chamada do algoritmo; leitura, parsing, criação do processo e validação ficam fora. Cada ponto de tempo usa três aquecimentos não contabilizados e 20 repetições. Operações rápidas são agrupadas em lotes calibrados: `elapsed_ns_total` preserva o lote e `elapsed_ns` representa uma chamada. Nenhum outlier válido é removido.

A memória é coletada separadamente no Windows por `PeakWorkingSet64` e `PeakPagedMemorySize64`. Cada ponto inicia 15 processos para o baseline e 15 para o algoritmo. O incremento é estimado por `max(0, mediana_algoritmo - mediana_baseline)`.

Execuções isoladas:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run-benchmarks.ps1 -Datasets datasets\04_cycle_6.graph
powershell -ExecutionPolicy Bypass -File .\tools\measure-memory.ps1 -Datasets datasets\04_cycle_6.graph
```

## Significado dos CSVs

- `results/raw/paired_timing.csv`: observações individuais de tempo dos dois algoritmos, nas duas linguagens, sobre a mesma suíte pareada;
- `results/raw/eulerian_scale_timing.csv`: escala de Hierholzer entre `V=1.000` e `V=32.000`;
- `results/raw/pilot_timing.csv`: busca do limite viável do caso hamiltoniano difícil, incluindo timeouts censurados;
- `results/raw/paired_memory.csv`: baseline e algoritmo nos caminhos pareados;
- `results/raw/eulerian_scale_memory.csv`: memória de Hierholzer na suíte grande;
- `results/summary/timing.csv`: média, mediana, desvio-padrão amostral, mínimo e máximo por ponto;
- `results/summary/memory.csv`: estatísticas de pico e incremento aproximado sobre o baseline;
- `results/summary/viability.csv`: maior `V` concluído e primeiro timeout por linguagem.

Os campos `status`, `timeout` e `valid` distinguem conclusão válida, falha e censura. Somente observações concluídas, válidas e não censuradas entram nos resumos; os dados censurados permanecem nos CSVs brutos.

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

O formato representa grafos simples e não direcionados, com vértices de `0` a `V-1`, sem laços ou arestas duplicadas e com exatamente `E` arestas depois de `EDGES`.

## Estrutura principal

```text
c/src/main.c                    implementações e interface em C17
python/src/                     implementações e interface em Python
tests/correctness.py            oráculos, validadores e testes cruzados
tools/generate_experiments.py   geração determinística da campanha
tools/run-benchmarks.ps1        coleta de tempo
tools/measure-memory.ps1        coleta de memória no Windows
tools/analyze.py                estatísticas, tabelas e SVGs
tools/run-experiments.ps1       campanha experimental completa
tools/run-all.ps1               validação rápida ou reprodução integral
tools/verify_project.py         auditoria de dados e documentos
datasets/                       grafos e manifesto de hashes
results/raw/                    observações individuais
results/summary/                tabelas consolidadas
results/charts/                 oito gráficos SVG
results/final-manifest.json     fontes, hashes e comandos finais
relatorio.md                    relatório nos sete itens exigidos
```

## Solução de problemas

- **`python` abre a Microsoft Store ou não é encontrado:** execute `where.exe python`, desative o alias de execução do Windows ou informe um Python instalado no `PATH`.
- **`gcc` não é encontrado:** abra um terminal MSYS2 UCRT64 ou acrescente `C:\msys64\ucrt64\bin` ao `PATH`.
- **scripts PowerShell são bloqueados:** use exatamente `powershell -ExecutionPolicy Bypass -File ...`; a alteração vale somente para esse processo.
- **`WinError 4551`/Controle de Aplicativo:** o teste de corretude repete temporariamente a criação do processo. Se a política continuar bloqueando `graph_solver.exe`, autorize a pasta do projeto ou execute em um terminal permitido pela instituição.
- **o modo integral parece parado:** os casos `V=16` das duas linguagens atingem intencionalmente 60 segundos cada; aguarde a mensagem da fase seguinte.
- **hash de gráfico ou dataset divergiu:** não edite artefatos gerados manualmente; rode `-Full` para reconstruí-los a partir das fontes.

Código-fonte: [repositório no GitHub](https://github.com/luccarissato/trabalho-teoria).

# Template PDF de importacao de carteira

Gere o PDF a partir desta tabela mantendo os cabecalhos exatamente como abaixo.
O parser backend aceita tabelas extraidas por `pdfplumber` ou texto com campos
separados por virgula, tabulacao ou multiplos espacos.

| ticker | quantity | average_price | asset_type |
| --- | ---: | ---: | --- |
| PETR4 | 100 | 32.50 | stock |
| VALE3 | 60 | 68.10 | stock |
| ITSA4 | 180 | 10.20 | stock |


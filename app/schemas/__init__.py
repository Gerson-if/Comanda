"""
Camada de Schemas — validação e serialização (Marshmallow).

Cada schema valida os dados de entrada (ex: payload de criação de produto)
antes de chegar ao service, e serializa os models para JSON/dict de saída
de forma consistente, evitando expor campos sensíveis (ex: password_hash).
"""

"""
Camada de Services — regras de negócio.

Cada service orquestra um ou mais repositórios para executar um caso de
uso completo (ex: "criar pedido" envolve validar estoque/preços, criar
Order + OrderItems, atualizar Customer, disparar envio de WhatsApp).
Controllers chamam services; services nunca conhecem detalhes de HTTP
(request, response, session) — isso mantém a lógica de negócio testável
sem precisar de um contexto Flask completo.
"""

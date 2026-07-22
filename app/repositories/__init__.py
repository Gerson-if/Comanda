"""
Camada de Repositórios — acesso a dados (queries SQLAlchemy).

Cada repositório concreto encapsula as queries de uma entidade e, quando
aplicável, herda de TenantScopedRepository para garantir isolamento
multi-tenant automático. Controllers e Services nunca fazem
`Model.query` diretamente; sempre passam por um repositório.
"""

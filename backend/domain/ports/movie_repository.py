"""
Puerto (Port) de persistencia — contrato que el dominio exige a cualquier
implementación de almacenamiento de películas.

Definido en el dominio, implementado en infraestructura.
El dominio nunca importa SQLite, Postgres u otro adaptador concreto.
"""

from abc import ABC, abstractmethod

from domain.entities import VibeConstraints


class MovieRepository(ABC):
    """
    Contrato de acceso a datos de películas.

    Los métodos son síncronos porque el repositorio de referencia es SQLite
    (IO local). La capa de aplicación usa run_in_threadpool() para no bloquear
    el event-loop de asyncio. Si en el futuro se migra a un motor async
    (asyncpg, Motor), este puerto puede evolucionar a async sin cambiar el dominio.
    """

    @abstractmethod
    def find_movies(self, constraints: VibeConstraints) -> list[dict]:
        """
        Devuelve hasta 100 películas que satisfacen las VibeConstraints.
        Retorna lista vacía si no hay resultados (nunca lanza).
        Cada dict contiene al menos:
          tconst, primaryTitle, startYear, genres, averageRating, numVotes, runtimeMinutes
        """
        ...

    @abstractmethod
    def count_all(self) -> int:
        """Cuenta el total de películas en la fuente de datos."""
        ...

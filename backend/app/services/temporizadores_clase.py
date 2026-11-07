"""Temporizadores por clase editada: "pasó un rato sin cambios, o la soltó". Los usan
las sugerencias de CU16 y el historial de CU18, que reaccionan al mismo momento.
"""

import asyncio
from collections.abc import Callable

# (proyecto, usuario, clase)
Clave = tuple[int, int, str]


class TemporizadoresPorClase:
    def __init__(self, al_vencer: Callable[[Clave], None]):
        self._al_vencer = al_vencer
        self._tareas: dict[Clave, asyncio.Task] = {}

    def programar(self, clave: Clave, espera: float) -> None:
        pendiente = self._tareas.get(clave)
        if pendiente:
            pendiente.cancel()
        self._tareas[clave] = asyncio.create_task(self._esperar(clave, espera))

    async def _esperar(self, clave: Clave, espera: float) -> None:
        await asyncio.sleep(espera)
        del self._tareas[clave]
        self._al_vencer(clave)

    def cancelar(self, coincide: Callable[..., bool]) -> None:
        for clave in [c for c in self._tareas if coincide(c)]:
            self._tareas.pop(clave).cancel()

    def soltar(self, proyecto_id: int, usuario_id: int, salvo: str | None = None) -> None:
        """Vence ya lo de ese usuario: soltó la clase, así que no hay más que esperar."""
        for clave in [c for c in self._tareas if c[0] == proyecto_id and c[1] == usuario_id and c[2] != salvo]:
            self._tareas.pop(clave).cancel()
            self._al_vencer(clave)

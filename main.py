import asyncio
import threading
import tempfile
import os
from queue import Queue, Empty
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk
from bleak import BleakScanner

from pybricksdev.connections.pybricks import PybricksHubBLE


# =========================================================
# Ventana selección de dispositivo BLE
# =========================================================

class DeviceSelectWindow(ctk.CTkToplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback

        self.title("Buscar HUB LEGO")
        self.geometry("400x400")
        self.attributes("-topmost", True)
        self.grab_set()

        self.label = ctk.CTkLabel(self, text="Escaneando dispositivos BLE...")
        self.label.pack(pady=10)

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(expand=True, fill="both", padx=10, pady=10)

        threading.Thread(target=self._scan, daemon=True).start()

    def _scan(self):
        loop = asyncio.new_event_loop()
        devices = loop.run_until_complete(BleakScanner.discover(timeout=4.0))
        loop.close()
        self.after(0, lambda: self._show(devices))

    def _show(self, devices):
        self.label.configure(text="Seleccione su dispositivo:")
        for d in devices:
            if d.name:
                btn = ctk.CTkButton(
                    self.scroll,
                    text=f"{d.name}\n{d.address}",
                    command=lambda dev=d: self._select(dev)
                )
                btn.pack(fill="x", pady=4)

    def _select(self, device):
        self.callback(device)
        self.destroy()


# =========================================================
# Generación de programa Pybricks
# =========================================================

def crear_programa(comando: str) -> str:
    COMANDOS = {
        "base_izq": "motor_D.dc(-500)",
        "base_der": "motor_D.run(500)",

        "muneca_arr": "motor_F.dc(500)",
        "muneca_abj": "motor_F.dc(-500)",

        "brazo_arr": "motor_B.dc(800)",
        "brazo_abj": "motor_B.dc(-800)",

        "garra_abrir": "motor_C.dc(500)",
        "garra_cerrar": "motor_C.dc(-500)",

        "detener_todo": """
motor_D.stop()
motor_F.stop()
motor_B.stop()
motor_C.stop()
"""
    }

    accion = COMANDOS.get(comando, COMANDOS["detener_todo"])

    return (f"""
from pybricks.pupdevices import Motor
from pybricks.parameters import Port, Direction

motor_D = Motor(Port.D, Direction.CLOCKWISE)
motor_F = Motor(Port.F, Direction.CLOCKWISE)
motor_B = Motor(Port.B, Direction.CLOCKWISE)
motor_C = Motor(Port.C, Direction.CLOCKWISE)

{accion}
""")


async def ejecutar_programa(hub, comando, registrar_log):
    codigo = crear_programa(comando)
    print (codigo)

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as archivo:
        archivo.write(codigo)
        ruta = archivo.name

    try:
        await hub.run(ruta, wait=False)
        registrar_log(f"Comando enviado: {comando}")
    except Exception as error:
        registrar_log(f"Error ejecución: {error}")
    finally:
        os.unlink(ruta)


# =========================================================
# Conexión BLE (asyncio + thread)
# =========================================================

class ConexionBLE:
    def __init__(self, cola_log):
        self.loop = asyncio.new_event_loop()
        self.cola_comandos = asyncio.Queue()
        self.hilo = threading.Thread(target=self._ejecutar_loop, daemon=True)
        self.hub = None
        self.dispositivo = None
        self.cola_log = cola_log

    def set_dispositivo(self, dispositivo):
        self.dispositivo = dispositivo

    def registrar_log(self, mensaje):
        self.cola_log.put(mensaje)

    def iniciar(self):
        if not self.dispositivo:
            self.registrar_log("❌ No hay dispositivo seleccionado")
            return
        if not self.hilo.is_alive():
            self.hilo.start()

    def enviar_comando(self, comando):
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(
                self.cola_comandos.put_nowait, comando
            )

    def _ejecutar_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.create_task(self._principal())
        self.loop.run_forever()

    async def _principal(self):
        try:
            self.registrar_log(f"Conectando a {self.dispositivo.name}...")
            self.hub = PybricksHubBLE(self.dispositivo)
            await self.hub.connect()
            self.registrar_log("Conectado ✔")

            while True:
                comando = await self.cola_comandos.get()
                await ejecutar_programa(self.hub, comando, self.registrar_log)

        except Exception as error:
            self.registrar_log(f"Error BLE: {error}")


# =========================================================
# Interfaz gráfica
# =========================================================

class Interfaz:
    def __init__(self, raiz):
        self.raiz = raiz
        self.raiz.title("Control LEGO SPIKE")
        self.raiz.geometry("480x520")

        self.cola_log = Queue()
        self.conexion = ConexionBLE(self.cola_log)

        self.crear_interfaz()
        self.actualizar_log()

    def crear_interfaz(self):
        ttk.Button(
            self.raiz,
            text="Conectar",
            command=self.abrir_selector
        ).pack(pady=10)

        marco = ttk.Frame(self.raiz)
        marco.pack()

        self.crear_boton(marco, "Base ←", "base_izq", 0, 0)
        self.crear_boton(marco, "Base →", "base_der", 0, 1)

        self.crear_boton(marco, "Muñeca ↑", "muneca_arr", 1, 0)
        self.crear_boton(marco, "Muñeca ↓", "muneca_abj", 1, 1)

        self.crear_boton(marco, "Brazo ↑", "brazo_arr", 2, 0)
        self.crear_boton(marco, "Brazo ↓", "brazo_abj", 2, 1)

        self.crear_boton(marco, "Abrir Garra", "garra_abrir", 3, 0)
        self.crear_boton(marco, "Cerrar Garra", "garra_cerrar", 3, 1)

        ttk.Button(
            self.raiz,
            text="STOP EMERGENCIA",
            command=lambda: self.conexion.enviar_comando("detener_todo")
        ).pack(pady=10)

        self.texto_log = tk.Text(self.raiz, height=8, state="disabled")
        self.texto_log.pack(fill="both", expand=True, padx=5, pady=5)

    def crear_boton(self, padre, texto, comando, fila, columna):
        boton = ttk.Button(padre, text=texto, width=18)
        boton.grid(row=fila, column=columna, padx=5, pady=8)
        boton.bind(
            "<ButtonPress>",
            lambda e: self.conexion.enviar_comando(comando)
        )
        boton.bind(
            "<ButtonRelease>",
            lambda e: self.conexion.enviar_comando("detener_todo")
        )

    def abrir_selector(self):
        DeviceSelectWindow(self.raiz, self.dispositivo_seleccionado)

    def dispositivo_seleccionado(self, dispositivo):
        self.cola_log.put(f"Dispositivo seleccionado: {dispositivo.name}")
        self.conexion.set_dispositivo(dispositivo)
        self.conexion.iniciar()

    def actualizar_log(self):
        try:
            while True:
                mensaje = self.cola_log.get_nowait()
                self.texto_log.config(state="normal")
                self.texto_log.insert("end", mensaje + "\n")
                self.texto_log.see("end")
                self.texto_log.config(state="disabled")
        except Empty:
            pass

        self.raiz.after(150, self.actualizar_log)


# =========================================================
# Main
# =========================================================

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    raiz = tk.Tk()
    Interfaz(raiz)
    raiz.mainloop()

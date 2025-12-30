import asyncio
import threading
import tempfile
import os
from queue import Queue, Empty

import customtkinter as ctk
from bleak import BleakScanner
from pybricksdev.connections.pybricks import PybricksHubBLE

CODIGO_GATEWAY_HUB = """
from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor
from pybricks.parameters import Port, Direction
from pybricks.tools import wait
import uselect, usys

hub = PrimeHub()

motor_base = Motor(Port.D, Direction.CLOCKWISE)
motor_muneca = Motor(Port.F, Direction.CLOCKWISE)
motor_brazo = Motor(Port.B, Direction.CLOCKWISE)
motor_garra = Motor(Port.C, Direction.CLOCKWISE)

motor_base.reset_angle(0)
motor_muneca.reset_angle(0)
motor_brazo.reset_angle(0)
motor_garra.reset_angle(0)

poll = uselect.poll()
poll.register(usys.stdin, uselect.POLLIN)

hub.display.char('A')

while True:
    if poll.poll(10):
        comando = usys.stdin.read(2)

        # BASE
        if comando == 'D+':
            motor_base.run(100)
        elif comando == 'D-':
            motor_base.run(-100)

        # MUÑECA (límites)
        elif comando == 'F+' and motor_muneca.angle() < 85:
            motor_muneca.run(35)
        elif comando == 'F-' and motor_muneca.angle() > -185:
            motor_muneca.run(-35)

        # BRAZO
        elif comando == 'B+':
            motor_brazo.run(25)
        elif comando == 'B-':
            motor_brazo.run(-25)

        # GARRA
        elif comando == 'C+':
            motor_garra.run(35)
        elif comando == 'C-':
            motor_garra.run(-35)

        # STOP GENERAL
        elif comando == 'ST':
            motor_base.stop()
            motor_muneca.stop()
            motor_brazo.stop()
            motor_garra.stop()

    wait(20)
"""

class WorkerBLE:
    def __init__(self, cola_logs: Queue):
        self.bucle = asyncio.new_event_loop()
        self.hilo = threading.Thread(target=self._hilo_principal, daemon=True)
        self.cola_comandos = None
        self.hub = None
        self.en_ejecucion = threading.Event()
        self.cola_logs = cola_logs
        self.dispositivo_objetivo = None
        self.solicitud_conexion = asyncio.Event()

    def log(self, mensaje: str):
        self.cola_logs.put(mensaje)

    def iniciar(self):
        if not self.hilo.is_alive():
            self.hilo.start()

    def _hilo_principal(self):
        asyncio.set_event_loop(self.bucle)
        self.bucle.create_task(self._ejecutor())
        self.bucle.run_forever()

    async def _ejecutor(self):
        ruta_temp = None
        while True:
            await self.solicitud_conexion.wait()
            try:
                self.log("Conectando al hub...")
                self.hub = PybricksHubBLE(self.dispositivo_objetivo)
                await self.hub.connect()

                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".py", delete=False, encoding="utf-8"
                ) as archivo:
                    archivo.write(CODIGO_GATEWAY_HUB)
                    ruta_temp = archivo.name

                self.log("Instalando controlador en el hub...")
                self.cola_comandos = asyncio.Queue()
                asyncio.create_task(self.hub.run(ruta_temp))

                self.en_ejecucion.set()
                self.log("LISTO - Control habilitado")

                while self.en_ejecucion.is_set():
                    comando = await self.cola_comandos.get()
                    await self.hub.write(comando.encode())

            except Exception as error:
                self.log(f"Error BLE: {error}")

            finally:
                if ruta_temp and os.path.exists(ruta_temp):
                    os.unlink(ruta_temp)
                if self.hub:
                    await self.hub.disconnect()
                self.en_ejecucion.clear()
                self.solicitud_conexion.clear()
                self.log("Hub desconectado")

    def conectar(self, dispositivo):
        self.dispositivo_objetivo = dispositivo
        self.bucle.call_soon_threadsafe(self.solicitud_conexion.set)

    def enviar(self, comando: str):
        if self.en_ejecucion.is_set() and self.cola_comandos:
            self.bucle.call_soon_threadsafe(self.cola_comandos.put_nowait, comando)

class VentanaSeleccionDispositivo(ctk.CTkToplevel):
    def __init__(self, padre, callback_seleccion):
        super().__init__(padre)
        self.callback_seleccion = callback_seleccion

        self.title("Buscar Hub LEGO")
        self.geometry("400x450")
        self.attributes("-topmost", True)
        self.grab_set()

        ctk.CTkLabel(
            self,
            text="Dispositivos encontrados",
            font=("Arial", 14, "bold")
        ).pack(pady=10)

        self.frame_scroll = ctk.CTkScrollableFrame(self, width=350, height=300)
        self.frame_scroll.pack(expand=True, fill="both", padx=10)

        ctk.CTkButton(self, text="Escanear", command=self.escanear).pack(pady=10)
        self.escanear()

    def escanear(self):
        for w in self.frame_scroll.winfo_children():
            w.destroy()
        threading.Thread(target=self._hilo_escaner, daemon=True).start()

    def _hilo_escaner(self):
        bucle = asyncio.new_event_loop()
        dispositivos = bucle.run_until_complete(BleakScanner.discover(timeout=3))
        bucle.close()
        self.after(0, lambda: self._actualizar(dispositivos))

    def _actualizar(self, dispositivos):
        for dispositivo in dispositivos:
            if dispositivo.name:
                ctk.CTkButton(
                    self.frame_scroll,
                    text=dispositivo.name,
                    command=lambda d=dispositivo: self._seleccionar(d),
                ).pack(fill="x", padx=10, pady=5)

    def _seleccionar(self, dispositivo):
        self.callback_seleccion(dispositivo)
        self.destroy()

class InterfazBrazo:
    def __init__(self, raiz):
        self.raiz = raiz
        self.raiz.title("Control Brazo LEGO")
        self.raiz.geometry("1440x720")

        self.cola_logs = Queue()
        self.trabajador = WorkerBLE(self.cola_logs)
        self.trabajador.iniciar()

        self._construir_ui()
        self._procesar_logs()

    def _construir_ui(self):
        barra_superior = ctk.CTkFrame(self.raiz)
        barra_superior.pack(fill="x", padx=20, pady=15)

        ctk.CTkButton(
            barra_superior,
            text="BUSCAR HUB",
            command=self.abrir_selector
        ).pack(side="left", padx=10)

        self.estado = ctk.CTkLabel(
            barra_superior,
            text="● DESCONECTADO",
            text_color="red"
        )
        self.estado.pack(side="right", padx=15)

        self.texto_logs = ctk.CTkTextbox(self.raiz, height=160)
        self.texto_logs.pack(fill="both", padx=20, pady=15)
        self.texto_logs.configure(state="disabled")

        self._crear_botones()

    def _crear_botones(self):
        self._boton("BASE ◀", "D-", 0.2, 0.25)
        self._boton("BASE ▶", "D+", 0.8, 0.25)
        self._boton("MUÑECA ▲", "F+", 0.5, 0.37)
        self._boton("MUÑECA ▼", "F-", 0.5, 0.49)
        self._boton("BRAZO ▲", "B+", 0.8, 0.37)
        self._boton("BRAZO ▼", "B-", 0.8, 0.49)
        self._boton("GARRA +", "C+", 0.2, 0.37)
        self._boton("GARRA -", "C-", 0.2, 0.49)

    def _boton(self, texto, comando, x, y):
        boton = ctk.CTkButton(self.raiz, text=texto, width=140, height=50)
        boton.place(relx=x, rely=y, anchor="center")
        boton.bind("<ButtonPress-1>", lambda e: self.trabajador.enviar(comando))
        boton.bind("<ButtonRelease-1>", lambda e: self.trabajador.enviar("ST"))

    def abrir_selector(self):
        VentanaSeleccionDispositivo(self.raiz, self.trabajador.conectar)

    def _procesar_logs(self):
        try:
            while True:
                mensaje = self.cola_logs.get_nowait()
                self.texto_logs.configure(state="normal")
                self.texto_logs.insert("end", f"> {mensaje}\n")
                self.texto_logs.see("end")
                self.texto_logs.configure(state="disabled")

                if "LISTO" in mensaje:
                    self.estado.configure(text="● CONECTADO", text_color="green")
                if "desconectado" in mensaje.lower():
                    self.estado.configure(text="● DESCONECTADO", text_color="red")

        except Empty:
            pass

        self.raiz.after(100, self._procesar_logs)

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    raiz = ctk.CTk()
    InterfazBrazo(raiz)
    raiz.mainloop()

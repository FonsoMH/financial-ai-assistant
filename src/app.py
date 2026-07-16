from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Creamos la aplicación de FastAPI (esta es la variable "app" que busca Uvicorn)
app = FastAPI(title="Sofía AI - Backend")

# Configuramos CORS para que tu móvil (React Native) pueda hablar con Python sin bloqueos de seguridad
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En desarrollo permitimos todos los orígenes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    """Ruta de prueba para verificar que la API funciona"""
    return {"status": "ok", "message": "Backend de Sofía AI funcionando perfectamente"}
#!/usr/bin/env python3
"""
Bot de Telegram para descargar videos de Instagram
Autor: @TuNombre
"""
import logging
import re
import os
import tempfile
import uuid
from urllib.parse import urlparse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import requests

# ==================== CONFIGURACIÓN ====================
# ¡REEMPLAZA ESTO CON TU TOKEN DE BOTFATHER!
BOT_TOKEN = "8544918906:AAGR6WDhACpp-Z1zVDhKENTGLXSK5trqs9Q"

# Directorio temporal para descargas
DOWNLOAD_DIR = tempfile.gettempdir()
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB (límite de Telegram)

# ==================== LOGGING ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== FUNCIONES UTILES ====================
def extract_instagram_url(text: str) -> str:
    """Extrae URL de Instagram del texto"""
    patterns = [
        r'https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/([a-zA-Z0-9_-]+)',
        r'https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/([a-zA-Z0-9_-]+)/?',
        r'instagram\.com/(?:p|reel|tv)/([a-zA-Z0-9_-]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            # Reconstruir URL completa
            shortcode = match.group(1)
            return f"https://www.instagram.com/reel/{shortcode}/"
    
    return None

def clean_filename(url: str) -> str:
    """Crea un nombre de archivo seguro"""
    parsed = urlparse(url)
    path = parsed.path.rstrip('/')
    filename = os.path.basename(path) or f"video_{uuid.uuid4().hex[:8]}"
    # Remover caracteres no seguros
    filename = re.sub(r'[^\w\-_.]', '_', filename)
    return f"instagram_{filename}.mp4"

def download_from_ddinstagram(url: str) -> dict:
    """
    Descarga video usando el servicio ddinstagram.com
    (Servicio público gratuito)
    """
    try:
        # Convertir URL de Instagram a ddinstagram
        dd_url = url.replace("instagram.com", "ddinstagram.com")
        
        # Hacer la solicitud
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        response = requests.get(dd_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return {"error": f"Error {response.status_code} al acceder al servicio"}
        
        # Buscar el video en la respuesta HTML
        html_content = response.text
        
        # Patrones para encontrar el video
        video_patterns = [
            r'<meta property="og:video" content="([^"]+)"',
            r'<meta property="og:video:url" content="([^"]+)"',
            r'<video[^>]+src="([^"]+)"',
            r'<source[^>]+src="([^"]+)"',
            r'"video_url":"([^"]+)"'
        ]
        
        video_url = None
        for pattern in video_patterns:
            match = re.search(pattern, html_content)
            if match:
                video_url = match.group(1)
                # Si es una URL relativa, hacerla absoluta
                if video_url.startswith('//'):
                    video_url = 'https:' + video_url
                elif video_url.startswith('/'):
                    video_url = 'https://ddinstagram.com' + video_url
                break
        
        if not video_url:
            # Buscar enlaces de descarga directa
            download_patterns = [
                r'href="(https?://[^"]+\.mp4[^"]*)"',
                r'src="(https?://[^"]+\.mp4[^"]*)"'
            ]
            for pattern in download_patterns:
                matches = re.findall(pattern, html_content)
                if matches:
                    video_url = matches[0]
                    break
        
        if video_url:
            return {
                "success": True,
                "video_url": video_url,
                "source": "ddinstagram"
            }
        else:
            return {"error": "No se pudo encontrar el video en la página"}
            
    except Exception as e:
        logger.error(f"Error en ddinstagram: {str(e)}")
        return {"error": f"Error del servidor: {str(e)}"}

def download_from_snapinsta(url: str) -> dict:
    """
    Alternativa usando snapinsta.app
    """
    try:
        api_url = "https://snapinsta.app/api/ajaxSearch"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': 'https://snapinsta.app',
            'Referer': 'https://snapinsta.app/',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        # Extraer el código corto de Instagram
        shortcode_match = re.search(r'/(p|reel|tv)/([a-zA-Z0-9_-]+)', url)
        if not shortcode_match:
            return {"error": "URL de Instagram no válida"}
        
        shortcode = shortcode_match.group(2)
        
        data = {
            'q': url,
            't': 'media',
            'lang': 'es'
        }
        
        response = requests.post(api_url, headers=headers, data=data, timeout=30)
        
        if response.status_code == 200:
            json_data = response.json()
            
            # Intentar diferentes estructuras de respuesta
            video_url = None
            
            if 'data' in json_data:
                data_html = json_data['data']
                
                # Buscar enlaces de video
                video_patterns = [
                    r'download_video":"([^"]+)"',
                    r'href="([^"]+\.mp4)"',
                    r'src="([^"]+\.mp4)"',
                    r'data-video="([^"]+)"'
                ]
                
                for pattern in video_patterns:
                    match = re.search(pattern, data_html)
                    if match:
                        video_url = match.group(1)
                        # Decodificar caracteres escapados
                        video_url = video_url.replace('\\/', '/')
                        break
            
            if video_url:
                return {
                    "success": True,
                    "video_url": video_url,
                    "source": "snapinsta"
                }
        
        return {"error": "No se pudo obtener el video de snapinsta"}
        
    except Exception as e:
        logger.error(f"Error en snapinsta: {str(e)}")
        return {"error": f"Error del servidor: {str(e)}"}

def download_video_file(video_url: str, filename: str) -> str:
    """Descarga el archivo de video"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Encoding': 'identity',
            'Range': 'bytes=0-'
        }
        
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        
        # Descargar el video
        response = requests.get(video_url, headers=headers, stream=True, timeout=60)
        response.raise_for_status()
        
        # Verificar tamaño del archivo
        file_size = int(response.headers.get('content-length', 0))
        if file_size > MAX_FILE_SIZE:
            raise ValueError(f"El video es demasiado grande ({file_size/1024/1024:.1f}MB). Límite: {MAX_FILE_SIZE/1024/1024}MB")
        
        # Descargar y guardar
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # Verificar que el archivo se descargó correctamente
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            return filepath
        else:
            raise ValueError("El archivo descargado está vacío")
            
    except Exception as e:
        logger.error(f"Error descargando video: {str(e)}")
        # Limpiar archivo si existe
        if os.path.exists(filepath):
            os.remove(filepath)
        raise

# ==================== HANDLERS DEL BOT ====================
async def start(update: Update, context: CallbackContext):
    """Maneja el comando /start"""
    welcome_msg = (
        "🎬 *Bot Descargador de Instagram*\n\n"
        "¡Hola! Envíame un enlace de Instagram y te lo descargaré.\n\n"
        "✨ *Enlaces soportados:*\n"
        "• Reels\n"
        "• Posts con video\n"
        "• Videos de perfil\n\n"
        "📌 *Ejemplos:*\n"
        "`https://www.instagram.com/reel/Cxample123/`\n"
        "`https://instagram.com/p/ABC123DEF/`\n\n"
        "⚠️ *Notas:*\n"
        "• Solo contenido público\n"
        "• Máximo 50MB por video\n"
        "• Puede haber límites de tasa\n\n"
        "✍️ *Desarrollado por:* @TuBot"
    )
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def help_command(update: Update, context: CallbackContext):
    """Maneja el comando /help"""
    help_text = (
        "🆘 *Ayuda*\n\n"
        "📤 *Cómo usar:*\n"
        "1. Copia el enlace de Instagram\n"
        "2. Pégalo aquí\n"
        "3. Espera a que descargue el video\n"
        "4. ¡Listo!\n\n"
        "🔗 *Formatos aceptados:*\n"
        "• https://instagram.com/reel/CODIGO/\n"
        "• https://www.instagram.com/p/CODIGO/\n"
        "• https://instagram.com/tv/CODIGO/\n\n"
        "⚙️ *Comandos:*\n"
        "/start - Iniciar el bot\n"
        "/help - Mostrar esta ayuda\n"
        "/about - Información del bot\n\n"
        "📢 *Canal de actualizaciones:* @TuCanal"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def about_command(update: Update, context: CallbackContext):
    """Maneja el comando /about"""
    about_text = (
        "🤖 *Acerca de este bot*\n\n"
        "*Nombre:* Instagram Downloader Bot\n"
        "*Versión:* 2.0\n"
        "*Lenguaje:* Python\n"
        "*Librería:* python-telegram-bot\n\n"
        "⚡ *Características:*\n"
        "• Descarga rápida de videos\n"
        "• Soporte para múltiples formatos\n"
        "• Servicio gratuito\n\n"
        "🔒 *Privacidad:*\n"
        "• No almacenamos tus datos\n"
        "• Los videos se eliminan después de enviar\n\n"
        "👨💻 *Desarrollador:* @TuUsuario\n"
        "📚 *Código fuente:* GitHub.com/TuUsuario\n"
        "🐛 *Reportar errores:* @TuUsuario"
    )
    await update.message.reply_text(about_text, parse_mode='Markdown')

async def handle_message(update: Update, context: CallbackContext):
    """Maneja mensajes con enlaces de Instagram"""
    user = update.effective_user
    message_text = update.message.text
    
    logger.info(f"Usuario {user.id} ({user.username}) envió: {message_text[:50]}...")
    
    # Extraer URL de Instagram
    instagram_url = extract_instagram_url(message_text)
    
    if not instagram_url:
        await update.message.reply_text(
            "❌ *No es un enlace válido de Instagram*\n\n"
            "Por favor, envía un enlace como:\n"
            "`https://www.instagram.com/reel/Cxample123/`\n"
            "`https://instagram.com/p/ABC123DEF/`",
            parse_mode='Markdown'
        )
        return
    
    # Mostrar mensaje de procesamiento
    processing_msg = await update.message.reply_text(
        "⏳ *Procesando tu enlace...*\n"
        "Esto puede tomar unos segundos.",
        parse_mode='Markdown'
    )
    
    try:
        # Intentar con el primer servicio
        await processing_msg.edit_text("🔍 *Buscando video...* (1/2)", parse_mode='Markdown')
        result = download_from_ddinstagram(instagram_url)
        
        # Si falla, intentar con el segundo servicio
        if "error" in result:
            await processing_msg.edit_text("🔍 *Buscando video...* (2/2)", parse_mode='Markdown')
            result = download_from_snapinsta(instagram_url)
        
        # Verificar si se obtuvo el video
        if "error" in result:
            error_msg = result["error"]
            await processing_msg.edit_text(
                f"❌ *Error al obtener el video*\n\n"
                f"*Razón:* {error_msg}\n\n"
                f"*Posibles soluciones:*\n"
                f"1. Verifica que el enlace sea público\n"
                f"2. Intenta con otro video\n"
                f"3. El video puede ser muy grande\n"
                f"4. Espera unos minutos e inténtalo de nuevo",
                parse_mode='Markdown'
            )
            return
        
        # Descargar el archivo
        await processing_msg.edit_text("📥 *Descargando video...*", parse_mode='Markdown')
        
        filename = clean_filename(result["video_url"])
        filepath = download_video_file(result["video_url"], filename)
        
        # Obtener información del archivo
        file_size = os.path.getsize(filepath)
        file_size_mb = file_size / 1024 / 1024
        
        # Enviar el video
        await processing_msg.edit_text(f"📤 *Enviando video...* ({file_size_mb:.1f}MB)", parse_mode='Markdown')
        
        with open(filepath, 'rb') as video_file:
            await update.message.reply_video(
                video=video_file,
                caption=f"✅ *Video descargado exitosamente*\n\n"
                       f"📊 *Tamaño:* {file_size_mb:.1f}MB\n"
                       f"🔗 *Fuente:* {result['source']}\n"
                       f"👤 *Solicitado por:* @{user.username if user.username else user.id}\n\n"
                       f"🎬 *Disfruta tu video!*",
                parse_mode='Markdown',
                supports_streaming=True
            )
        
        # Eliminar mensaje de procesamiento
        await processing_msg.delete()
        
        logger.info(f"Video enviado exitosamente a {user.id}")
        
    except ValueError as e:
        await processing_msg.edit_text(f"❌ *Error:* {str(e)}", parse_mode='Markdown')
        logger.error(f"Error de valor: {str(e)}")
        
    except requests.exceptions.Timeout:
        await processing_msg.edit_text(
            "⏱️ *Tiempo de espera agotado*\n\n"
            "El servidor está tardando demasiado. Por favor, intenta de nuevo más tarde.",
            parse_mode='Markdown'
        )
        logger.error("Timeout en la descarga")
        
    except requests.exceptions.RequestException as e:
        await processing_msg.edit_text(
            "🌐 *Error de conexión*\n\n"
            "No se pudo conectar con el servidor. Verifica tu conexión a internet.",
            parse_mode='Markdown'
        )
        logger.error(f"Error de red: {str(e)}")
        
    except Exception as e:
        error_msg = str(e)
        await processing_msg.edit_text(
            f"⚠️ *Error inesperado*\n\n"
            f"```\n{error_msg[:200]}\n```\n\n"
            f"Por favor, reporta este error al desarrollador.",
            parse_mode='Markdown'
        )
        logger.error(f"Error inesperado: {str(e)}", exc_info=True)
        
    finally:
        # Limpiar archivo descargado
        try:
            if 'filepath' in locals() and os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"Archivo temporal eliminado: {filepath}")
        except Exception as e:
            logger.error(f"Error eliminando archivo temporal: {str(e)}")

async def error_handler(update: Update, context: CallbackContext):
    """Maneja errores no capturados"""
    logger.error(f"Error: {context.error}", exc_info=True)
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ *Ocurrió un error interno*\n\n"
            "El desarrollador ha sido notificado. Por favor, intenta de nuevo más tarde.",
            parse_mode='Markdown'
        )

# ==================== FUNCIÓN PRINCIPAL ====================
def main():
    """Función principal del bot"""
    # Verificar que el token esté configurado
    if BOT_TOKEN == "TU_TOKEN_AQUI":
        print("❌ ERROR: Debes configurar tu token en la variable BOT_TOKEN")
        print("1. Abre Telegram y busca @BotFather")
        print("2. Crea un bot con /newbot")
        print("3. Copia el token y pégalo en BOT_TOKEN")
        return
    
    print("🤖 Iniciando Bot de Descarga de Instagram...")
    print(f"📁 Directorio temporal: {DOWNLOAD_DIR}")
    print("📊 Límite de archivo: 50MB")
    print("🔗 Servicios: ddinstagram.com, snapinsta.app")
    print("🚀 Bot listo para recibir mensajes...")
    print("📢 Para detener: Ctrl+C")
    print("-" * 50)
    
    # Crear la aplicación
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Añadir handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    
    # Manejar mensajes de texto
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))
    
    # Manejar errores
    application.add_error_handler(error_handler)
    
    # Iniciar el bot
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()

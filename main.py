#!/usr/bin/env python

import os
import sys
import logging
import asyncio
from datetime import datetime
import tempfile
import shutil
import subprocess
import time
import math

# Verificar dependencias
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
    import yt_dlp
except ImportError as e:
    print(f"📦 Instalando dependencia faltante: {e}")
    os.system("pip install python-telegram-bot yt-dlp")
    print("✅ Dependencias instaladas. Reinicia el script.")
    sys.exit(0)

# Configuración del bot - Token de prueba (lo cambiarás después)
TOKEN = "8465187385:AAHfE5w9t1aYr5r5Ti1rRIuREAxRARw4xAs"

# Configurar logging para Railway
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Mensajes decorados
WELCOME_MESSAGE = """
╔══════════════════════════════╗
║  🎥 *INSTAGRAM VIDEO BOT*    ║
╚══════════════════════════════╝

✨ *¡Bienvenido!* ✨

📥 *Envíame cualquier enlace de Instagram:*
• Reels
• Posts con video
• Stories públicas

📌 *Comandos disponibles:*
/help - Ver ayuda
/about - Información
/stats - Estadísticas

_Desarrollado con ❤️ en Railway_
"""

HELP_MESSAGE = """
╔══════════════════════════════╗
║        📖 *AYUDA*            ║
╚══════════════════════════════╝

🎯 *¿Cómo usar?*

1️⃣ *Copia el enlace* del video de Instagram
2️⃣ *Pégalo aquí* en el chat
3️⃣ *Espera* mientras descargo
4️⃣ *¡Recibe tu video!*

📝 *Ejemplos de enlaces:*
• `https://www.instagram.com/p/Cx...`
• `https://www.instagram.com/reel/D...`
• `https://www.instagram.com/tv/C...`

⚠️ *Nota:* Solo videos públicos
"""

ABOUT_MESSAGE = """
╔══════════════════════════════╗
║      ℹ️ *INFORMACIÓN*        ║
╚══════════════════════════════╝

🤖 *Bot:* Instagram Video Downloader
📦 *Versión:* 3.5.0
⚙️ *Motor:* yt-dlp (actualizado)
☁️ *Plataforma:* Railway

✨ *Características:*
✅ Descarga directa
✅ Alta calidad
✅ Barra de progreso
✅ Sin marcas de agua
✅ Optimizado para Railway

👨‍💻 *Desplegado en:* Railway.app
"""

# Estadísticas
stats = {
    'total_users': set(),
    'total_downloads': 0,
    'successful': 0,
    'failed': 0,
    'download_times': [],
    'start_time': datetime.now()
}

class ProgressHook:
    """Clase para manejar el progreso de descarga"""
    def __init__(self, message, update, context):
        self.message = message
        self.update = update
        self.context = context
        self.last_update = 0
        self.progress_message = ""
        self.animation_frames = ["⬜", "⬛"]
        
    def progress_hook(self, d):
        if d['status'] == 'downloading':
            # Actualizar cada 2 segundos para no sobrecargar
            current_time = time.time()
            if current_time - self.last_update > 2:
                try:
                    # Obtener porcentaje
                    if '_percent_str' in d:
                        percent_str = d['_percent_str'].strip()
                        percent = float(percent_str.replace('%', ''))
                    else:
                        return
                    
                    # Calcular velocidad y ETA
                    speed = d.get('_speed_str', 'N/A')
                    eta = d.get('_eta_str', 'N/A')
                    
                    # Crear barra de progreso visual
                    bar_length = 15
                    filled = int(bar_length * percent // 100)
                    bar = '█' * filled + '░' * (bar_length - filled)
                    
                    # Animación simple
                    frame = self.animation_frames[int(current_time * 2) % 2]
                    
                    # Formatear mensaje
                    progress_text = f"""
{frame} *Descargando video...*

📊 *Progreso:* {percent:.1f}%
{bar}  {percent:.1f}%

⚡ *Velocidad:* {speed}
⏱️ *ETA:* {eta}

_Por favor espera..._
"""
                    # Usar asyncio para actualizar el mensaje
                    asyncio.create_task(
                        self.message.edit_text(progress_text, parse_mode='Markdown')
                    )
                    self.last_update = current_time
                    
                except Exception as e:
                    logger.error(f"Error actualizando progreso: {e}")
                    
        elif d['status'] == 'finished':
            asyncio.create_task(
                self.message.edit_text(
                    "✅ *Descarga completada!*\n\n📤 *Procesando video...*",
                    parse_mode='Markdown'
                )
            )

async def download_instagram_video(url: str, progress_message, update, context):
    """
    Descarga un video de Instagram usando yt-dlp con barra de progreso
    """
    start_time = datetime.now()
    
    # Crear directorio temporal
    temp_dir = tempfile.mkdtemp()
    output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
    
    try:
        # Crear hook de progreso
        progress_hook = ProgressHook(progress_message, update, context)
        
        # Configurar opciones de yt-dlp
        ydl_opts = {
            'outtmpl': output_template,
            'format': 'best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'noplaylist': True,
            'progress_hooks': [progress_hook.progress_hook],
        }
        
        # Descargar el video
        logger.info(f"Descargando: {url}")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extraer información
            info = ydl.extract_info(url, download=True)
            
            if info is None:
                return None, "No se pudo obtener información del video"
            
            # Buscar el archivo descargado
            video_file = None
            for file in os.listdir(temp_dir):
                if file.endswith(('.mp4', '.mkv', '.webm', '.mov')):
                    video_file = os.path.join(temp_dir, file)
                    break
            
            if not video_file:
                return None, "No se encontró el archivo de video"
            
            # Calcular tiempo
            download_time = (datetime.now() - start_time).total_seconds()
            
            # Obtener título
            title = info.get('title', 'Video de Instagram')
            if len(title) > 50:
                title = title[:50] + "..."
            
            # Actualizar estadísticas
            stats['total_downloads'] += 1
            stats['successful'] += 1
            stats['download_times'].append(download_time)
            
            return video_file, title
            
    except Exception as e:
        logger.error(f"Error en descarga: {str(e)}")
        # Limpiar directorio temporal
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Actualizar estadísticas de error
        stats['total_downloads'] += 1
        stats['failed'] += 1
        
        return None, str(e)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start"""
    user = update.effective_user
    stats['total_users'].add(user.id)
    
    keyboard = [
        [
            InlineKeyboardButton("📖 Ayuda", callback_data='help'),
            InlineKeyboardButton("ℹ️ Info", callback_data='about'),
            InlineKeyboardButton("📊 Stats", callback_data='stats')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        WELCOME_MESSAGE,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /help"""
    await update.message.reply_text(HELP_MESSAGE, parse_mode='Markdown')

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /about"""
    await update.message.reply_text(ABOUT_MESSAGE, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /stats"""
    total_users = len(stats['total_users'])
    total_downloads = stats['total_downloads']
    successful = stats['successful']
    failed = stats['failed']
    success_rate = (successful / total_downloads * 100) if total_downloads > 0 else 0
    uptime = datetime.now() - stats['start_time']
    hours = uptime.total_seconds() // 3600
    minutes = (uptime.total_seconds() % 3600) // 60
    
    stats_message = f"""
╔══════════════════════════════╗
║      📊 *ESTADÍSTICAS*       ║
╚══════════════════════════════╝

👥 *Usuarios únicos:* {total_users}
🎥 *Descargas totales:* {total_downloads}
✅ *Exitosas:* {successful}
❌ *Fallidas:* {failed}
📈 *Tasa de éxito:* {success_rate:.1f}%

⏱️ *Tiempo promedio:* {sum(stats['download_times'])/len(stats['download_times']) if stats['download_times'] else 0:.1f}s
🕒 *Uptime:* {int(hours)}h {int(minutes)}m

_Actualizado: {datetime.now().strftime("%H:%M:%S")}_
"""
    await update.message.reply_text(stats_message, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los callbacks de los botones"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'help':
        await query.edit_message_text(HELP_MESSAGE, parse_mode='Markdown')
    elif query.data == 'about':
        await query.edit_message_text(ABOUT_MESSAGE, parse_mode='Markdown')
    elif query.data == 'stats':
        total_users = len(stats['total_users'])
        total_downloads = stats['total_downloads']
        successful = stats['successful']
        failed = stats['failed']
        success_rate = (successful / total_downloads * 100) if total_downloads > 0 else 0
        uptime = datetime.now() - stats['start_time']
        hours = uptime.total_seconds() // 3600
        minutes = (uptime.total_seconds() % 3600) // 60
        
        stats_message = f"""
╔══════════════════════════════╗
║      📊 *ESTADÍSTICAS*       ║
╚══════════════════════════════╝

👥 *Usuarios únicos:* {total_users}
🎥 *Descargas totales:* {total_downloads}
✅ *Exitosas:* {successful}
❌ *Fallidas:* {failed}
📈 *Tasa de éxito:* {success_rate:.1f}%

⏱️ *Tiempo promedio:* {sum(stats['download_times'])/len(stats['download_times']) if stats['download_times'] else 0:.1f}s
🕒 *Uptime:* {int(hours)}h {int(minutes)}m

_Actualizado: {datetime.now().strftime("%H:%M:%S")}_
"""
        await query.edit_message_text(stats_message, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los mensajes con enlaces"""
    
    text = update.message.text
    
    # Verificar si es enlace de Instagram
    if 'instagram.com' not in text:
        keyboard = [[InlineKeyboardButton("📖 Ver ayuda", callback_data='help')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "❌ *Enlace no válido*\n\n"
            "Por favor envía un enlace de Instagram que contenga:\n"
            "• `instagram.com/p/...`\n"
            "• `instagram.com/reel/...`\n"
            "• `instagram.com/tv/...`",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    # Mensaje de procesamiento inicial
    processing_msg = await update.message.reply_text(
        "🔍 *Verificando enlace...*\n⏳ Un momento por favor",
        parse_mode='Markdown'
    )
    
    try:
        # Descargar el video con barra de progreso
        video_path, title = await download_instagram_video(
            text, processing_msg, update, context
        )
        
        if video_path is None:
            await processing_msg.delete()
            await update.message.reply_text(
                f"❌ *Error al descargar*\n\n🔍 {title}\n\n"
                "💡 *Posibles causas:*\n"
                "• El video es privado\n"
                "• El enlace no es válido\n"
                "• Instagram bloqueó la descarga",
                parse_mode='Markdown'
            )
            return
        
        # Obtener tamaño del archivo
        file_size = os.path.getsize(video_path) / (1024 * 1024)  # Convertir a MB
        
        # Mensaje de finalización
        await processing_msg.delete()
        
        # Enviar el video con información
        with open(video_path, 'rb') as video:
            caption = f"""
✅ *¡Video descargado exitosamente!*

📹 *Título:* {title}
📦 *Tamaño:* {file_size:.1f} MB
⏱️ *Tiempo:* {stats['download_times'][-1]:.1f}s

✨ *¡Disfruta tu video!*
"""
            # Usar send_video para mejor compatibilidad
            await update.message.reply_video(
                video=video,
                caption=caption,
                parse_mode='Markdown',
                supports_streaming=True,
                filename=f"instagram_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            )
        
        # Limpiar archivos temporales
        try:
            os.remove(video_path)
            shutil.rmtree(os.path.dirname(video_path), ignore_errors=True)
        except:
            pass
        
    except Exception as e:
        await processing_msg.delete()
        error_msg = str(e)
        logger.error(f"Error inesperado: {error_msg}")
        
        await update.message.reply_text(
            f"❌ *Error inesperado*\n\n"
            f"🔍 {error_msg[:200]}\n\n"
            f"🔄 Por favor intenta con otro video",
            parse_mode='Markdown'
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja errores del bot"""
    logger.error(f"Error en update {update}: {context.error}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ *Ocurrió un error*\n\n"
                "Por favor intenta de nuevo más tarde",
                parse_mode='Markdown'
            )
    except:
        pass

def main():
    """Función principal para Railway"""
    
    # Verificar token
    if not TOKEN:
        logger.error("No se encontró el token del bot")
        print("❌ Error: No se encontró el token del bot")
        print("Por favor configura el token en el código")
        sys.exit(1)
    
    # Crear la aplicación
    application = Application.builder().token(TOKEN).build()
    
    # Añadir manejadores
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Añadir manejador de errores
    application.add_error_handler(error_handler)
    
    # Mensaje de inicio para Railway
    port = os.environ.get('PORT', 8080)
    print("╔════════════════════════════════════════╗")
    print("║   🤖 Bot de Instagram para Railway     ║")
    print("║   🟢 Iniciado correctamente            ║")
    print("╚════════════════════════════════════════╝")
    print(f"📊 Estadísticas inicializadas")
    print(f"🌐 Puerto: {port}")
    print(f"⏰ Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Presiona Ctrl+C para detener")
    
    # Configurar webhook para Railway
    railway_url = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
    if railway_url:
        webhook_url = f"https://{railway_url}/webhook"
        application.run_webhook(
            listen="0.0.0.0",
            port=int(port),
            url_path=TOKEN,
            webhook_url=f"{webhook_url}/{TOKEN}"
        )
    else:
        # Modo polling si no hay webhook configurado
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

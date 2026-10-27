"""User-facing text in English and Spanish. The language follows the system;
set CLAWDY_LANG=en or CLAWDY_LANG=es to override it."""
import locale
import os
import re
import subprocess
import sys

STRINGS = {
    "limit.session": ("Session (5h)", "Sesión (5h)"),
    "limit.weekly": ("Weekly", "Semanal"),
    "limit.weekly_model": ("Weekly {model}", "Semanal {model}"),
    "limit.extra": ("Extra usage (month)", "Uso extra (mes)"),
    "limit.other": ("Other limit", "Otro límite"),
    "short.session": ("5h", "5h"),
    "short.weekly": ("wk", "sem"),
    "short.extra": ("extra", "extra"),

    "time.now": ("now", "ya"),
    "time.resets_in": ("resets in {t}", "se reinicia en {t}"),
    "time.updated": ("updated {t}", "actualizado {t}"),

    "panel.title": ("Claude usage", "Uso de Claude"),
    "status.loading": ("loading usage…", "cargando uso…"),
    "status.waiting": ("checking again in {t}", "esperando {t} para consultar"),
    "error.rate_limited": ("rate limited, retrying later", "límite de consultas, reintento luego"),
    "error.renew": ("open Claude Code to renew your session", "abre Claude Code para renovar la sesión"),
    "error.login": ("sign in to Claude Code", "inicia sesión en Claude Code"),
    "error.offline": ("no internet connection", "sin conexión a internet"),
    "need.install": ("Click to see your usage", "Clic para ver tu uso"),
    "need.login": ("Click to sign in", "Clic para iniciar sesión"),
    "need.opened": ("finish in the terminal window", "termina en la ventana de terminal"),
    "need.installing": ("installing Claude Code…", "instalando Claude Code…"),
    "need.browser": ("approve in your browser", "aprueba en tu navegador"),
    "need.ask_title": ("See your Claude usage", "Ver tu uso de Claude"),
    "need.ask": ("To show your usage, Clawdy needs Claude Code (free with your Claude plan).\n\n"
                 "Install it and sign in now? Your browser will open so you can approve.",
                 "Para mostrar tu uso, Clawdy necesita Claude Code (gratis con tu plan de Claude).\n\n"
                 "¿Instalarlo e iniciar sesión ahora? Se abrirá tu navegador para que lo apruebes."),
    "need.ask_login": ("Sign in to Claude Code so Clawdy can show your usage?\n\n"
                       "Your browser will open so you can approve.",
                       "¿Iniciar sesión en Claude Code para que Clawdy muestre tu uso?\n\n"
                       "Se abrirá tu navegador para que lo apruebes."),

    "act.thinking": ("Thinking…", "Pensando…"),
    "act.typing": ("Writing code", "Escribiendo código"),
    "act.typing.short": ("Writing", "Escribiendo"),
    "act.building": ("Running commands", "Ejecutando comandos"),
    "act.building.short": ("Commands", "Comandos"),
    "act.reading": ("Reading files", "Leyendo archivos"),
    "act.reading.short": ("Reading", "Leyendo"),
    "act.groove": ("With 1 subagent", "Con 1 subagente"),
    "act.groove.short": ("1 subagent", "1 subagente"),
    "act.juggling": ("Juggling subagents", "Malabares con subagentes"),
    "act.juggling.short": ("Subagents", "Subagentes"),
    "act.error": ("Something failed!", "¡Algo falló!"),
    "act.notification": ("Needs you", "Te necesita"),
    "act.sweeping": ("Compacting context", "Compactando contexto"),
    "act.sweeping.short": ("Compacting", "Compactando"),
    "act.happy": ("Done!", "¡Terminó!"),

    "say.boo": ("Boo!", "¡Bu!"),
    "say.ho": ("Ho ho!", "¡Jo jo!"),

    "chat.app": ("chat in the app", "chat en la app"),
    "chat.web": ("chat on claude.ai", "chat en claude.ai"),

    "update.available": ("v{v} · click to update", "v{v} · clic para actualizar"),
    "update.applying": ("updating…", "actualizando…"),
    "update.offline": ("can't reach GitHub", "sin conexión con GitHub"),
    "update.latest": ("you're up to date", "ya tienes la última versión"),
    "update.failed": ("update failed", "no se pudo actualizar"),
    "update.no_installer": ("installer not found", "no encontré el instalador"),
    "update.no_package": ("package not found", "no encontré el paquete"),
    "update.no_mac": ("Mac build not found", "no encontré la versión para Mac"),
    "update.bad_zip": ("the download has no app", "el archivo descargado no trae la app"),
    "update.cancelled": ("update cancelled", "actualización cancelada"),
    "update.finish": ("open the installer to finish", "abre el instalador para terminar"),
    "update.manual": ("download it from the project page", "descárgala en la página del proyecto"),
    "update.scoop": ("run: scoop update clawdy", "ejecuta: scoop update clawdy"),

    "menu.chat_app": ("New chat in the app", "Nuevo chat en la app"),
    "menu.chat_web": ("New chat on claude.ai", "Nuevo chat en claude.ai"),
    "menu.refresh": ("Refresh usage now", "Actualizar uso ahora"),
    "menu.updates": ("Check for updates", "Buscar actualizaciones"),
    "menu.hooks": ("React to Claude Code", "Reaccionar a Claude Code"),
    "menu.autostart": ("Open at login", "Abrir al encender"),
    "menu.pin": ("Keep panel open", "Panel siempre abierto"),
    "menu.walks": ("Walks around the desktop", "Paseos por el escritorio"),
    "menu.alerts": ("Alert near limits", "Avisar cerca del límite"),
    "menu.sounds": ("Sounds", "Sonidos"),
    "menu.tasks": ("Notify when Claude finishes", "Avisar cuando Claude termina"),
    "menu.done_after": ("Notify for tasks longer than", "Avisar si la tarea tarda más de"),
    "menu.share": ("Share my usage", "Compartir mi uso"),
    "menu.settings": ("Settings", "Ajustes"),
    "task.done_title": ("✅ Claude finished", "✅ Claude terminó"),
    "task.done_body": ("{where} · took {t}", "{where} · tardó {t}"),
    "task.done_short": ("Done!", "¡Listo!"),
    "task.ask_title": ("✋ Claude needs you", "✋ Claude te necesita"),
    "task.permission": ("{where} · waiting for your permission", "{where} · espera tu permiso"),
    "task.ask_short": ("Needs you!", "¡Te necesita!"),
    "share.title": ("My Claude usage", "Mi uso de Claude"),
    "share.no_data": ("no usage yet", "aún sin datos"),
    "share.saved": ("image saved ✓", "imagen guardada ✓"),
    "share.failed": ("could not save it", "no se pudo guardar"),
    "share.post": ("My Claude usage today, tracked by Clawdy 👾 a pixel buddy for your desktop. Free & open source: {link} #ClaudeCode",
                   "Mi uso de Claude hoy, con Clawdy 👾 un compañero pixel para tu escritorio. Gratis y open source: {link} #ClaudeCode"),
    "alert.title": ("{name} at {p}%", "{name} al {p} %"),
    "alert.body": ("Claude usage · resets in {t}", "Uso de Claude · se reinicia en {t}"),
    "alert.body_nr": ("Claude usage", "Uso de Claude"),
    "alert.short": ("{name} at {p}%!", "¡{name} al {p} %!"),
    "sessions.title": ("Claude Code", "Claude Code"),
    "sessions.open": ("Open now", "Abiertas ahora"),
    "sessions.recent": ("Recent chats", "Chats recientes"),
    "sessions.new": ("New chat in…", "Nuevo chat en…"),
    "sessions.none": ("No Claude Code chats yet", "Aún no hay chats de Claude Code"),
    "sessions.cant_focus": ("can't switch windows here", "no puedo cambiar de ventana aquí"),
    "sessions.yesterday": ("yesterday", "ayer"),
    "menu.size": ("Size", "Tamaño"),
    "menu.costume": ("Costume", "Disfraz"),
    "menu.quit": ("Quit", "Salir"),
    "menu.hide": ("Hide (keep in tray)", "Ocultar (sigue en la bandeja)"),
    "tray.show": ("Show Clawdy", "Mostrar Clawdy"),
    "tray.hide": ("Hide Clawdy", "Ocultar Clawdy"),
    "size.small": ("Small", "Chico"),
    "size.normal": ("Normal", "Normal"),
    "size.large": ("Large", "Grande"),
    "costume.auto": ("Auto", "Auto"),
    "costume.none": ("None", "Ninguno"),
    "costume.witch": ("Witch", "Bruja"),
    "costume.pumpkin": ("Pumpkin", "Calabaza"),
    "costume.ghost": ("Ghost", "Fantasma"),
    "costume.vampire": ("Vampire", "Vampiro"),
    "costume.santa": ("Santa", "Noel"),

    "welcome.title": ("Welcome to Clawdy", "Bienvenido a Clawdy"),
    "welcome.hi": ("Hi! I'm Clawdy", "¡Hola! Soy Clawdy"),
    "welcome.intro": ("I show you how much of your Claude plan you've used. And while Claude Code "
                      "works, I act it out: thinking, typing, hammering…",
                      "Te muestro cuánto llevas usado de Claude. Y mientras Claude Code trabaja, "
                      "yo hago lo mismo que él: pienso, escribo, martillo…"),
    "welcome.no_login": ("Your usage comes from Claude Code, which isn't set up on this computer yet "
                         "(the desktop app alone isn't enough). I can set it up for you:",
                         "Tu uso viene de Claude Code, que aún no está configurado en esta computadora "
                         "(la app de escritorio sola no basta). Puedo configurarlo por ti:"),
    "welcome.connect": ("Connect my usage now (you'll approve in your browser)",
                        "Conectar mi uso ahora (lo apruebas en tu navegador)"),
    "welcome.hooks": ("React to what Claude Code is doing", "Reaccionar a lo que hace Claude Code"),
    "welcome.autostart": ("Open me when the computer starts", "Abrirme al encender la computadora"),
    "welcome.hint": ("You can change this anytime by right-clicking me.",
                     "Puedes cambiarlo cuando quieras con clic derecho sobre mí."),
    "welcome.start": ("Get started", "Empezar"),

    "system.read_settings": ("Couldn't read the Claude Code settings ({e}).",
                             "No pude leer la configuración de Claude Code ({e})."),
    "system.save_settings": ("Couldn't save the Claude Code settings ({e}).",
                             "No pude guardar la configuración de Claude Code ({e})."),
    "system.autostart": ("Couldn't set up opening at login ({e}).",
                         "No pude configurar el inicio automático ({e})."),
    "system.desktop_comment": ("Your Claude usage, with an animated buddy",
                               "Tu uso de Claude, con un compañero animado"),
    "run.no_tk": ("tkinter is missing. On Ubuntu/Debian: sudo apt install python3-tk",
                  "Falta tkinter. En Ubuntu/Debian: sudo apt install python3-tk"),
}


def _system_language():
    forced = os.environ.get("CLAWDY_LANG")
    if forced:
        return forced
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        if os.environ.get(var):
            return os.environ[var]
    if sys.platform == "win32":
        try:
            import ctypes
            return locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), "")
        except Exception:
            pass
    if sys.platform == "darwin":
        # GUI apps on macOS get no LANG; the preferred languages live in the user defaults.
        try:
            out = subprocess.run(["defaults", "read", "-g", "AppleLanguages"],
                                 capture_output=True, text=True, timeout=3).stdout
            match = re.search(r"[A-Za-z]{2}", out)
            if match:
                return match.group(0)
        except Exception:
            pass
    try:
        return locale.getlocale()[0] or ""
    except Exception:
        return ""


LANG = "es" if _system_language().lower().startswith("es") else "en"


def t(key, **kw):
    en, es = STRINGS[key]
    text = es if LANG == "es" else en
    return text.format(**kw) if kw else text

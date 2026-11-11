"""Notification: avisa en Windows cuando Claude Code necesita a Robert (toast nativo, sin dependencias)."""

import json
import platform
import subprocess
import sys

msg = json.load(sys.stdin).get("message", "Claude Code necesita tu atención")
msg = msg.replace("'", "").replace('"', "")[:120]
if platform.system() == "Windows":
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null;"
        "$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(1);"
        "$t.GetElementsByTagName('text')[0].AppendChild($t.CreateTextNode('LAY dev: " + msg + "')) > $null;"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('LAY').Show("
        "[Windows.UI.Notifications.ToastNotification]::new($t))"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
else:
    print("\a", end="")

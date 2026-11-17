#!/bin/sh
# Instala (ou reinstala) o agendamento mensal do VAU no launchd do usuário.
# Rodar uma vez neste Mac: sh scripts/instalar_agendamento.sh
#
# O agente roda a partir de um clone próprio em ~/.acecalculos: o macOS não
# deixa processos em segundo plano lerem ~/Documents sem autorização manual.
set -e
LABEL=com.acecalculos.vau
REMOTE=git@github.com:lucasalmeida80/acecalculos.git
CLONE="$HOME/.acecalculos"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ -d "$CLONE/.git" ]; then
  git -C "$CLONE" pull -q --ff-only origin main
else
  git clone -q "$REMOTE" "$CLONE"
fi
git -C "$CLONE" config user.name "Lucas Almeida"
git -C "$CLONE" config user.email "lucasalmeida80@users.noreply.github.com"
chmod +x "$CLONE/scripts/atualiza_vau.py"

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
sed -e "s|__REPO__|$CLONE|g" -e "s|__HOME__|$HOME|g" "$CLONE/scripts/$LABEL.plist" > "$DEST"
plutil -lint "$DEST"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DEST"
launchctl print "gui/$(id -u)/$LABEL" | grep -E "state|program" | head -3
echo "Instalado: $DEST (roda em $CLONE)"
echo "Para rodar agora e testar:  launchctl kickstart gui/$(id -u)/$LABEL"
echo "Log: $HOME/Library/Logs/acecalculos-vau.log"

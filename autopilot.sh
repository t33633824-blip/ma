#!/usr/bin/env bash
# Один цикл автопилота: найти темы и сделать N роликов. Для cron:
#   crontab -e  →  0 9 * * * /home/ИМЯ/shorts/autopilot.sh 3 >> /home/ИМЯ/shorts/out/autopilot.log 2>&1
cd "$(dirname "$0")"
COUNT="${1:-3}"
echo "=== $(date '+%F %T') autopilot: $COUNT роликов"
./shorts.sh discover --count "$COUNT" || echo "discover завершился с ошибкой, пробую очередь как есть"
./shorts.sh run --count "$COUNT"

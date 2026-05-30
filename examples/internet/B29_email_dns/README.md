# B29 Email (SEED DNS + SMTP/IMAP)

A realistic multi-ISP, multi-IX email system using SEED DNS/MX records, AS-local DNS caches, real Postfix/Dovecot mail servers, transport-map delivery, and a Roundcube webmail frontend. This is the single source of truth for running and validating the B29 scenario.

- Internet Map: http://localhost:18080/pro/home
- Roundcube: http://localhost:8082

## Status
- Clean, internally validated demo scenario (no ad-hoc hot patches).
- Deterministic classroom setup; demo-mode security (DKIM/DMARC/SPF not enforced).
- Runtime validation checks per-message tokens in the recipient mailbox, not only historical log entries.

## Requirements
- Linux host with Docker
- Either docker compose or docker-compose
- Python 3 (no manual PYTHONPATH needed; orchestrator sets it)

## Quick Start (Integrated)
```bash
cd examples/internet/B29_email_dns

# WSL/Docker pre-check. If it warns about bridge netfilter, run the printed sudo sysctl line.
bash b29ctl.sh doctor

# Optional image warm-up for slow Docker Hub links.
# These tags match docker-compose-roundcube.yml after retagging.
docker pull docker.m.daocloud.io/library/mariadb:10.11
docker tag docker.m.daocloud.io/library/mariadb:10.11 mariadb:10.11
docker pull docker.1ms.run/roundcube/roundcubemail:latest
docker tag docker.1ms.run/roundcube/roundcubemail:latest roundcube/roundcubemail:latest

# Start everything (generate -> up -> accounts -> Roundcube)
bash b29ctl.sh start            # auto-detects platform via uname; uses docker compose or docker-compose

# Cross-domain tests (primary providers only)
bash b29ctl.sh test

# Cross-domain tests (all six providers)
bash b29ctl.sh test --all

# Custom test pairs file
cat > pairs.txt << 'EOF'
user@qq.com user@gmail.com
user@gmail.com user@qq.com
user@163.com user@outlook.com
admin@company.cn user@gmail.com
founder@startup.net user@qq.com
EOF
bash b29ctl.sh test --pairs pairs.txt
```

## Quick Verify (optional)
- Cross-AS data plane:
```bash
docker exec as202h-host_0-10.202.0.71 ping -c 2 10.200.0.71
docker exec mail-gmail-google ping -c 2 10.200.0.10
```

- DNS MX from AS-150 cache
```bash
cd examples/internet/B29_email_dns/output
docker exec as150h-dns-cache-10.150.0.53 nslookup -type=mx qq.com
docker exec as150h-dns-cache-10.150.0.53 nslookup -type=mx gmail.com
```

- Cross-domain (CLI samples)
```bash
# QQ -> Gmail
printf "Subject: QQ->Gmail\nFrom: user@qq.com\nTo: user@gmail.com\n\nHi\n" | docker exec -i mail-qq-tencent sendmail -f user@qq.com -t
# Outlook -> Company (use admin@company.cn)
printf "Subject: Outlook->Company\nFrom: user@outlook.com\nTo: admin@company.cn\n\nHi\n" | docker exec -i mail-outlook-microsoft sendmail -f user@outlook.com -t
# Startup -> 163 (use founder@startup.net)
printf "Subject: Startup->163\nFrom: founder@startup.net\nTo: user@163.com\n\nHi\n" | docker exec -i mail-startup-selfhosted sendmail -f founder@startup.net -t
```

- Check delivery logs (look for Saved/status=sent)
```bash
cd ~/seed-playground/seed-emulator-harness-codex/examples/internet/B29_email_dns
for f in \
  output/mail-gmail-google-data/mail-logs/mail.log \
  output/mail-company-aliyun-data/mail-logs/mail.log \
  output/mail-163-netease-data/mail-logs/mail.log
{ do echo "=== $f ==="; [ -f "$f" ] && grep -E "Saved|status=sent" "$f" | tail -n 20 || echo missing; echo; }; done
```

- Optional: disable milters at runtime for deterministic tests
```bash
cd output
for c in mail-qq-tencent mail-163-netease mail-gmail-google mail-outlook-microsoft mail-company-aliyun mail-startup-selfhosted; do
  docker exec "$c" sh -c "postconf -e smtpd_milters= && postconf -e non_smtpd_milters= && postconf -e milter_default_action=accept && postfix reload" || true
done
cd ..
```

- Cross-domain (full matrix) via helper
```bash
cd examples/internet/B29_email_dns
bash b29ctl.sh test --all
```

## Cleanup
```bash
cd examples/internet/B29_email_dns
bash b29ctl.sh stop
```

## Notes
- Demo-only configuration. Do not use in production.
- Run a single internet-map example at a time to avoid resource/port conflicts.

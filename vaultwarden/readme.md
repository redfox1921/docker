## Hash erzeugen

Verbinde dich per SSH, zum Beispiel mit `ssh benutzer@server-ip`, und führe den Befehl aus.
Der Befehl ist interaktiv und fragt zweimal nach dem Passwort:

```bash
docker run --rm -it vaultwarden/server:latest /vaultwarden hash
```

## Hash eintragen

Die Ausgabe ist der `$argon2id$...`-String. Du trägst ihn als `ADMIN_TOKEN` ein.

- In einer `docker-compose.yml` musst du jedes `$` im Hash als `$$` schreiben, sonst versucht Compose, es als Variable aufzulösen.
- In einer `.env`-Datei oder bei `docker run -e` setzt du den Hash in einfache Anführungszeichen.

```yaml
environment:
  ADMIN_TOKEN: '$$argon2id$$v=19$$m=65540,t=3,p=4$$...'
```

## Container neu starten und einloggen

Die Verwaltungsseite liegt unter `https://<deine-domain>/admin`.
Dort loggst du dich mit dem **Klartext-Passwort** ein, nicht mit dem Hash.

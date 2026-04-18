# pronote-mcp

Serveur qui connecte Claude Desktop à **Pronote** via l'ENT Monlycée Île-de-France.

## Fonctionnalités

Six outils disponibles dans Claude :

| Outil | Description |
|---|---|
| `pronote_get_schedule` | Emploi du temps sur une plage de dates |
| `pronote_get_homework` | Devoirs à faire (filtrés par date) |
| `pronote_get_recent_grades` | Dernières notes, toutes périodes confondues |
| `pronote_get_period_averages` | Moyennes par matière pour un trimestre/semestre |
| `pronote_get_lesson_content` | Contenu pédagogique d'un cours (description, fichiers) |
| `pronote_get_today_summary` | Résumé du jour : cours, devoirs et notes récentes |

## Prérequis

- Python 3.10+
- Un compte Monlycée (ENT Île-de-France) avec accès Pronote
- L'URL Pronote de l'établissement (ex. `https://XXXXX.index-education.net/pronote/eleve.html`)

## Installation


Depuis les sources :

```bash
git clone https://github.com/thomasgreissler/pronote-mcp
cd pronote-mcp
pip install -e .
```

## Configuration



```env
MONLYCEE_USER=prenom.nom@lycee.fr
MONLYCEE_PASS=votre_mot_de_passe
PRONOTE_URL=https://XXXXX.index-education.net/pronote/eleve.html
```



## Utilisation

### Mode stdio (Claude Desktop)

conf: (`claude_desktop_config.json`) :

```json
{
  "mcpServers": {
    "pronote": {
      "command": "pronote-mcp",
      "env": {
        "MONLYCEE_USER": "prenom.nom@lycee.fr",
        "MONLYCEE_PASS": "mdp",
        "PRONOTE_URL": "https://XXXXX.index-education.net/pronote/eleve.html"
      }
    }
  }
}
```

### Mode HTTP (ALPHA)

```bash
MCP_AUTH_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
pronote-mcp-http
```



## Variables d'environnement

| Variable | Obligatoire | Description |
|---|---|---|
| `MONLYCEE_USER` | Oui | Identifiant ENT Monlycée |
| `MONLYCEE_PASS` | Oui | Mot de passe ENT Monlycée |
| `PRONOTE_URL` | Oui | URL de l'espace élève Pronote |
| `MCP_AUTH_TOKEN` | HTTP uniquement | Token Bearer (min. 24 caractères) |
| `MCP_HTTP_HOST` | Non | Adresse d'écoute (défaut : `127.0.0.1`) |
| `MCP_HTTP_PORT` | Non | Port d'écoute (défaut : `8765`) |

## Licence

MIT

# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it by:

1. **Do NOT** open a public issue
2. Email the maintainers directly or use GitHub's private vulnerability reporting
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and work on a fix.

## Security Best Practices

When using this tool:

1. **Keep secrets secure**: Never commit `config.json` with real tokens
2. **Use environment variables**: For CI/CD, use environment variables instead of config files
3. **Limit permissions**: Run with minimal required permissions
4. **Update regularly**: Keep dependencies up to date
5. **Review logs**: Monitor for unusual activity

## Configuration Security

The `config.json` file contains sensitive information:

- Telegram bot tokens
- Discord webhook URLs
- Email credentials
- HMAC secrets

**Always**:
- Add `config.json` to `.gitignore` (already done by default)
- Use `config.example.json` as a template
- Store production secrets in secure vaults or environment variables

# DuckDNS da Venus AI

O token nunca entra no Git. Na EC2, mantenha o domínio e o token em
`/etc/duckdns/update.env`, com permissão `600`, e use o timer abaixo para
atualizar o registro quando o IPv4 público mudar.

O serviço deve usar um subdomínio estável, como `venus-ai.duckdns.org`, e o
Nginx/Let's Encrypt deve usar esse mesmo nome. O mobile deve apontar para o
hostname, nunca para o IP da instância.

Arquivos:

- `venus-ai-duckdns.service`: atualiza o registro DuckDNS;
- `venus-ai-duckdns.timer`: executa na inicialização e a cada cinco minutos.

Instale-os na EC2 em `/etc/systemd/system/`, crie o `update.env` fora do
repositório e execute `systemctl daemon-reload` e `systemctl enable --now
venus-ai-duckdns.timer`.

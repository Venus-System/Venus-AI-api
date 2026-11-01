# Deploy da Venus AI na EC2

A conta AWS Academy não permite criar a role IAM necessária para OIDC do GitHub Actions. Para manter o custo em zero, o deploy usa a própria EC2 v2: um timer do systemd verifica origin/develop a cada minuto e inicia o serviço de deploy somente quando o commit remoto mudou.

## Instalação

Na raiz do clone /opt/venus-ai:

    sudo install -m 0755 deploy/venus-ai-deploy-check.sh /usr/local/sbin/venus-ai-deploy-check
    sudo install -m 0644 deploy/venus-ai-deploy-poller.service /etc/systemd/system/venus-ai-deploy-poller.service
    sudo install -m 0644 deploy/venus-ai-deploy-poller.timer /etc/systemd/system/venus-ai-deploy-poller.timer
    sudo systemctl daemon-reload
    sudo systemctl enable --now venus-ai-deploy-poller.timer

O serviço existente venus-ai-deploy.service continua responsável por fazer o git pull, construir a imagem e recriar o contêiner. O timer apenas dispara esse serviço quando há mudança; ele não reconstrói a imagem a cada minuto.

## Verificação

    systemctl is-active venus-ai-deploy-poller.timer
    systemctl list-timers venus-ai-deploy-poller.timer

Essa alternativa não cria EC2, Load Balancer, NAT Gateway, CloudWatch ou outro recurso cobrado. O intervalo de até um minuto é o compromisso para usar somente a instância já existente.

# e-SUS Cast — Fase 1

Prova de conceito para exibir um painel fictício do Windows em uma Roku TV pela rede local. O servidor entrega JPEG de 1280 × 720 com uma senha fictícia, número do quadro e horário de referência. A Roku consulta a imagem aproximadamente a cada dois segundos e usa um `Poster` do SceneGraph para exibi-la em tela cheia, mantendo a proporção.

- [Servidor Windows](sender-windows/sender.py)
- [Receptor Roku](receiver-roku/)
- [ZIP de sideload](dist/esus-cast-roku.zip)
- [Scripts de instalação, execução e empacotamento](scripts/)
- [Testes automatizados](tests/test_fase1.py)

## 1. Preparar o Windows

Instale Python 3.10 ou posterior com o comando `python` disponível no terminal. No PowerShell, a partir da pasta do projeto, execute:

```powershell
.\scripts\preparar-windows.cmd
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
python .\scripts\empacotar_roku.py
```

A preparação cria `.venv` e instala Pillow. Se o proxy impedir o acesso ao índice, a TI pode fornecer o wheel de Pillow 12.3.0 para a versão e a arquitetura do Python instalado. Com o wheel em uma pasta local, execute `.\scripts\preparar-windows.cmd --no-index --find-links C:\caminho\dos\wheels`. Após a instalação, o servidor funciona na rede local. O empacotador coloca o `manifest` na raiz de `dist\esus-cast-roku.zip`.

Para testar primeiro no próprio Windows, execute `.\scripts\iniciar-windows.cmd`. Abra `http://127.0.0.1:8766/frame.jpg?token=SEU_TOKEN` em um navegador e recarregue após alguns segundos. Devem aparecer quadros diferentes. Encerre com **Ctrl+C**.

## 2. Servir para a Roku

Encontre o IPv4 Ethernet do Windows com `ipconfig`. Na TV, veja o IPv4 em **Configurações → Rede → Sobre**. Ethernet e Wi-Fi podem estar em sub-redes diferentes, desde que a rede permita conexão nas duas direções usadas pelo teste.

Substitua os endereços de exemplo pelos endereços dos seus equipamentos:

```powershell
$ipWindows = '192.168.1.10'
$ipRoku = '192.168.1.20'
.\scripts\iniciar-windows.cmd --ip $ipWindows --roku $ipRoku --porta 8766
```

Deixe o terminal aberto e guarde o token exibido. O servidor escuta no IPv4 informado e exige tanto o IP autorizado da Roku quanto o token. O próprio Windows também pode consultar a imagem para diagnóstico. Cada execução gera um novo token, salvo quando se informa `--token` para repetir um teste de recuperação.

Se a política da unidade exigir uma regra de firewall, peça à TI entrada TCP na porta configurada, limitada ao IPv4 da Roku e ao perfil autorizado. Use dados fictícios e uma rede de teste autorizada. HTTP local envia JPEG e token sem criptografia. Equipamentos capazes de observar esse tráfego podem lê-los. Mantenha a porta restrita à LAN e solicite autorização da TI antes de instalar em equipamentos institucionais.

## 3. Instalar o receptor

1. A documentação da Roku orienta ter cadastro no programa de desenvolvedores. No controle da Roku, pressione **Home** três vezes, **Cima** duas vezes e, em seguida, **Direita, Esquerda, Direita, Esquerda, Direita**.
2. Na tela de desenvolvedor, anote o IP exibido, habilite o instalador, aceite os termos e defina a senha de desenvolvedor. Aguarde a reinicialização. A opção depende do aparelho e das permissões de desenvolvimento disponíveis.
3. No navegador do **Windows**, abra `http://IP_DA_ROKU`. Entre com o usuário `rokudev` e a senha definida na TV.
4. Use **Upload** para selecionar `dist\esus-cast-roku.zip` e **Install** para instalar. Se o instalador oferecer um tipo de compressão, a documentação da Roku indica **squashfs** para uma instalação mais rápida. O slot de desenvolvimento comporta um aplicativo por vez. Confirme antes de substituir um aplicativo de teste já instalado.
5. No receptor, preencha **IP do Windows**, **Porta** e **Token da sessão**. Selecione **Testar conexão**. A mensagem esperada é **Conexão OK. A Roku recebeu e abriu o JPEG.**
6. Selecione **Conectar**. A senha fictícia e o contador devem mudar. A tecla **Voltar** abre a configuração durante a reprodução. Após o primeiro quadro recebido, o receptor salva os parâmetros e tenta reconectar ao ser aberto de novo.

[Documentação de configuração de desenvolvedor da Roku](https://github.com/rokudev/dev-doc/blob/v2.0/docs/DEVELOPER/getting-started/developer-setup.md)

## 4. Validar o fluxo na TV

| Teste | Procedimento | Resultado a registrar |
| --- | --- | --- |
| Instalação | Carregue o ZIP pelo instalador | Modelo, versão do Roku OS e mensagem do instalador |
| Recepção | Use **Testar conexão** e depois **Conectar** | Mensagem exibida, legibilidade, proporção, atualização e eventual cintilação |
| Atraso | Filme no mesmo vídeo a TV e um relógio do próprio Windows com segundos. Use o primeiro instante visível de cada quadro e subtraia o horário impresso no JPEG do horário mostrado no Windows | Pelo menos dez amostras, mediana e maior atraso. Um relógio com segundos inteiros limita a precisão a cerca de um segundo |
| Interrupção | Pare o servidor com **Ctrl+C** por 15 segundos enquanto a TV exibe o painel | Tempo até sumir o quadro e aparecer **Aguardando conexão com o painel** |
| Reconexão | Reinicie com o mesmo IP e porta, acrescentando `--token TOKEN_ANTERIOR` | Tempo até voltar a atualizar, sem usar o controle |
| Reabertura | Saia do app e abra-o de novo com o servidor ativo | Se o painel voltou com os dados salvos |

O horário impresso marca quando o quadro fictício passou a valer, mesmo que seu JPEG só seja gerado na primeira consulta. A medida cobre o atraso da consulta e da exibição desse painel de teste. A latência da captura real será medida em outra fase.

Se o teste de conexão falhar, abra `http://IP_DO_WINDOWS:8766/frame.jpg?token=SEU_TOKEN` no Windows usando o IPv4 Ethernet. Se funcionar no PC, confirme o token e o IPv4 atuais na TV, a entrada TCP no firewall e, com a TI, o roteamento e o isolamento de clientes Wi-Fi. O acesso ao instalador da Roku testa Windows → TV. O botão **Testar conexão** verifica TV → Windows. Se o instalador apresentar erro, registre a mensagem e, se disponível, a saída do console de depuração da Roku em TCP 8085. Ao devolver resultados, inclua o modelo, versão do Roku OS, mensagens e tempos, mantendo o token e a senha de desenvolvedor privados.

## Escopo e referências

Esta fase usa Python/Pillow e JPEG para validar o caminho de rede e a exibição com poucas dependências. O receptor carrega um quadro por vez, troca a imagem após o carregamento e esconde a imagem anterior se a próxima consulta falhar. As tentativas usam espera crescente até 15 segundos. Captura do e-SUS, HLS, descoberta SSDP, comandos ECP, inicialização automática e testes prolongados pertencem às fases seguintes.

- [SceneGraph Poster](https://github.com/rokudev/dev-doc/blob/v2.0/docs/REFERENCES/scenegraph/renderable-nodes/poster.md) e [reprodução de vídeo em SceneGraph para a etapa HLS](https://github.com/rokudev/dev-doc/blob/v2.0/docs/DEVELOPER/core-concepts/playing-videos.md).
- [Roku External Control Protocol para etapas futuras](https://github.com/rokudev/dev-doc/blob/v2.0/docs/DEVELOPER/dev-tools/external-control-api.md).
- [Dowe LanCaster, referência de arquitetura](https://github.com/mrjohndowe/Dowe_LanCaster#features). A implementação do e-SUS Cast foi escrita do zero.

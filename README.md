# OpenShark

Painel Windows para Attack Shark R1, X6 e X11. Reúne bateria wireless na bandeja, aviso em 10%, DPI, polling, remapeamento, sensor, energia, perfis e biblioteca local de macros.

## Abrir

Execute `OpenShark/dist/OpenShark.exe` ou `Start OpenShark.bat`. Para usar o código fonte:

```powershell
python -m pip install -r requirements.txt
python OpenShark/main.py
```

Para reconstruir o executável portátil:

```powershell
python -m pip install pyinstaller
./build.ps1
```

## Uso

1. Conecte o dongle 2,4 GHz e desconecte o cabo USB do mouse para receber a bateria wireless.
2. O modelo é detectado automaticamente. Para receptores R1/X6 que compartilham identificadores, conecte o cabo uma vez: o app lembra a identidade do receptor neste PC.
3. Edite DPI, botões, sensor ou energia e clique em **Aplicar**. O rodapé só informa sucesso quando o receptor confirmar o relatório HID.
4. Use **Perfis** para criar, renomear, importar, exportar e aplicar conjuntos de ajustes. Os perfis ficam em `%LOCALAPPDATA%\OpenShark\profiles.json`.

O dongle não oferece leitura confiável das configurações atuais no R1/X6. Ao abrir o OpenShark, os valores apresentados vêm do perfil local; o app não envia ajustes automaticamente. Aplicar um relatório de DPI ou botões envia o mapa completo dessa seção, inclusive campos que não foram editados.

## Compatibilidade e validação

| Função | R1 | X6 | X11 |
| --- | --- | --- | --- |
| Bateria wireless | Testada no R1 físico: 100% | Decodificador com fonte pública | Decodificador com fonte pública |
| Polling 125/250/500/1000 Hz | Comando e ACK testados no R1 | Protocolo documentado | Protocolo documentado |
| DPI, estágio ativo, ripple, angle snap | Comando e ACK de DPI testados no R1 | Codificação X6 documentada | Codificação X11 documentada |
| Botões | Protocolo de família documentado; sem teste físico R1 | Capturas públicas X6 | Código e capturas públicas X11 |
| Energia e resposta dos botões | Codificação R1 documentada; sem teste físico | Capturas públicas X6 | Código público X11; sem teste físico |
| Macros | Edição e armazenamento local | Edição e armazenamento local | Edição e armazenamento local |

**ACK confirma que o dongle aceitou o pacote**, não mede o efeito físico de cada ajuste. No X6 e X11, a comunicação real ainda precisa ser testada com esses mouses. A biblioteca de macros ainda não grava macros no firmware; a interface indica isso. Outras linhas Attack Shark exigem identificação e protocolo próprios antes de receber controles de escrita.

No Windows, a presença do receptor `1D57:FA60` não significa que o mouse está em modo wireless. Quando o R1 está ligado pelo cabo (`1D57:FA61`), o painel mostra Carregando. A aplicação procura a interface HID de comandos do mesmo fabricante; se o dispositivo não a expuser pelo cabo, use o receptor 2,4 GHz para alterar configurações. O botão físico 6 atualiza o estágio de DPI destacado no painel. Sem leitura do dongle, a bateria mostra `—` em vez de um número estimado.

## Fontes do protocolo

- [R1: driver Odin com reports 04/05/06](https://github.com/xb-bx/attack-shark-r1-driver)
- [X6: capturas e documentação do receptor](https://github.com/blak0p/attack-shark-linux/blob/main/docs/protocol-captures.md)
- [X11: codificadores e documentação](https://github.com/HarukaYamamoto0/attack-shark-x11-driver)

A tabela PAW3311 usada no DPI do X11 é derivada de código MIT; veja [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md). A arte do mouse exibida no painel é carregada da pasta do software oficial já presente no computador, se disponível; não é incluída no executável. O OpenShark não é afiliado à Attack Shark.

## Atualizações (v0.3.0)

Em Configurações, use Verificar atualizações. O app consulta as releases públicas de GuelBDev/OpenShark, baixa OpenShark.exe e verifica o SHA-256 antes de instalar. A versão anterior é preservada como OpenShark.exe.bak.

O Windows controla a área visível da bandeja: ative OpenShark.exe nas configurações da barra ou arraste o ícone para fora da seta.
## Interface 0.4.0

A interface principal usa Qt/PySide6 6.8.3: painéis com gradientes reais, bordas iluminadas, marcadores laranja, controles alinhados e uma visualização 2D com o mouse no centro. Bateria, carregamento USB, estágio de DPI físico e atualizações continuam integrados ao monitor HID.

O código das telas está em `OpenShark/qt_ui.py`. A arte original é carregada da instalação local do usuário e não é distribuída no executável. Fora dessa instalação, a interface usa uma ilustração própria como alternativa. Qt/PySide6 usa a opção LGPLv3; os textos das licenças ficam em `OpenShark/assets/licenses`. Para reconstruir com bibliotecas compatíveis modificadas, altere a dependência em `requirements.txt`, instale-a e execute `build.ps1`.
## Instalador Windows

O instalador oficial está disponível em [Releases](https://github.com/GuelBDev/OpenShark/releases/latest).
Para gerar uma nova versão localmente, primeiro execute `build.ps1` na pasta do aplicativo e depois compile `installer.iss` com o Inno Setup 6 (`ISCC.exe installer.iss`). O instalador resultante será criado em `dist/OpenShark-Setup-<versão>.exe`.


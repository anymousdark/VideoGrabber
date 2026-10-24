# VideoGrabber 🎥

**Gravador de tela, webcam e áudio — sem limites.**

> **feito por [anymousdark](https://github.com/anymousdark)**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-22c55e)

---

## ✨ Recursos

- 🖥 **Gravação de tela inteira** (todos os monitores, seleção automática do principal)
- ✂️ **Gravação de região personalizada** — arraste o mouse para selecionar
- 🎥 **Gravação de webcam** com escolha de dispositivo
- 🧑‍🤝‍🧑 **Tela + webcam (picture-in-picture)** com posição e tamanho configuráveis
- 🎙 **Gravação de áudio** — microfone e/ou áudio do sistema (loopback)
- ⏯ **Pausar e retomar** sem cortar o arquivo
- ⏱ **Sem limite de tempo** (limites opcionais por minutos ou tamanho)
- 🎞 **Formatos**: MP4, AVI, MKV e WebM
- ⚙️ **FPS e qualidade ajustáveis**
- 🖱 **Cursor destacado** na gravação
- 📸 **Screenshot** rápido com atalho
- ⌨️ **Atalhos globais** (F9–F12)
- 🎨 **Interface escura moderna** em Tkinter (sem dependências pesadas de UI)
- 💾 **Configurações salvas** automaticamente em `settings.json`

---

## 📦 Instalação

### Opção 1 — Executável pronto

Baixe o `VideoGrabber.exe` na página de **[Releases](https://github.com/anymousdark/VideoGrabber/releases/latest)** e execute. Não precisa instalar Python.

> O Windows pode exibir um aviso do SmartScreen por ser um executável novo/independente.
> Clique em **Mais informações → Executar assim mesmo**.

### Opção 2 — Rodar pelo código

```bash
git clone https://github.com/anymousdark/VideoGrabber.git
cd VideoGrabber

python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

python main.py
```

Requisitos: **Python 3.10+** e Windows 10/11.

---

## 🎮 Como usar

1. Escolha o **modo**: Tela, Webcam, Tela + Cam ou Áudio.
2. Defina a **pasta de saída** e as opções (formato, FPS, limites).
3. Clique em **Iniciar gravação** (ou pressione **F9**).
4. Use **Pausar/Retomar** (F10) e **Parar** (F9) quando terminar.
5. O arquivo aparece na pasta escolhida.

### Atalhos

| Tecla | Ação |
|-------|------|
| `F9` | Iniciar / Parar gravação |
| `F10` | Pausar / Retomar |
| `F11` | Screenshot |
| `F12` | Mostrar / ocultar janela |

---

## 🔧 Gerar o executável

```bash
pip install -r requirements.txt
python build_exe.py
```

O executável será gerado em `dist/VideoGrabber.exe` e copiado para `release/VideoGrabber.exe`.

---

## 📝 Notas técnicas

- **Áudio do sistema**: no Windows, habilite **"Mixagem estéreo" (Stereo Mix)** nas propriedades de som, ou use um dispositivo de loopback (VB-Cable, etc.). O app detecta automaticamente dispositivos com nomes como *Stereo Mix*, *Wave Out*, *Loopback* ou *Monitor*.
- **Mesclagem de áudio + vídeo**: usa **FFmpeg** quando disponível. Sem FFmpeg, o vídeo é salvo e o áudio é mantido em um `.wav` separado.
- **Seleção de região**: cobre o monitor principal. Para múltiplos monitores, ajuste as coordenadas manualmente em `settings.json`.
- **Webcam PiP**: ative a opção *Webcam PiP* no modo Tela + Cam.
- **Gravação de janela específica**: disponível via `config.recording.target_window` (API), ainda sem campo na interface.

---

## 🗂 Estrutura

```
VideoGrabber/
├── main.py            # Ponto de entrada
├── gui.py             # Interface Tkinter
├── recorder.py        # Motor de captura (tela, webcam, áudio)
├── config.py          # Configurações e persistência
├── build_exe.py       # Build com PyInstaller
├── requirements.txt
├── release/           # saída local do build (o .exe fica nas Releases)
├── LICENSE
└── README.md
```

---

## ⚖️ Licença

MIT — use, modifique, distribua e venda. Veja [LICENSE](LICENSE).

**Créditos:** feito por **anymousdark**.

---

<p align="center">🎥 Feito com código aberto e sem limitações.</p>

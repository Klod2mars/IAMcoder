# Project Tree

```text
aihomecoder/
├── __init__.py
├── AIHomeCoder.bat
├── aihomecoder.yalm.yaml
├── config/
│   ├── profiles/
│   │   ├── deepseek_local.yaml
│   │   ├── default.yaml
│   │   └── qwen_local.yaml
│   └── settings.yaml
├── core/
│   ├── __init__.py
│   ├── file_manager.py
│   ├── guardrail.py
│   └── settings.py
├── data/
│   ├── __init__.py
│   ├── ai_connector.py
│   ├── context_index.py
│   ├── diff_engine.py
│   └── yaml_parser.py
├── deepseek_review_phase_03.yalm.yaml
├── domain/
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── diff_result.py
│   │   ├── mission.py
│   │   └── task.py
│   └── services/
│       ├── __init__.py
│       └── executor_service.py
├── example_mission.yalm
├── exchange/
│   ├── deepseek_to_qwen_review.lialm
│   └── qwen_to_deepseek_test.lialm
├── INSTALLATION.md
├── logs/
│   ├── deepseek_phase_03.log
│   ├── mission_output_phase_02.log
│   ├── session_20251030_134520.md
│   ├── session_20251030_134646.md
│   ├── session_20251030_140424.md
│   ├── session_20251030_140920.md
│   ├── session_20251030_140942.md
│   ├── session_20251030_144305.md
│   ├── session_20251030_144314.md
│   ├── session_20251030_144323.md
│   ├── session_20251030_153430.md
│   ├── session_20251030_153938.md
│   ├── session_20251030_154119.md
│   ├── session_20251030_155319.md
│   ├── session_20251030_155440.md
│   ├── session_20251030_161743.md
│   ├── session_20251030_162834.md
│   ├── session_20251030_163103.md
│   ├── session_20251030_170603.md
│   ├── session_20251030_170626.md
│   ├── session_20251030_171114.md
│   ├── session_20251030_171217.md
│   ├── session_20251030_171245.md
│   ├── session_20251030_173434.md
│   ├── session_20251030_173505.md
│   └── session_validation_phase1.md
├── main.py
├── mission_output_phase_02.yalm.yaml
├── mission_standard.yalm.yaml
├── modules/
│   ├── __init__.py
│   └── output_handler.py
├── presentation/
│   ├── __init__.py
│   ├── cli.py
│   ├── logger.py
│   └── ui_diff_view.py
├── README.md
├── reports/
│   ├── deepseek_review_output.md
│   └── mission_test_output.md
├── requirements.txt
├── run_mission.py
├── test_aihomecoder_phase1.yalm_files/
│   ├── 0b9ddda9-6221-47c5-8769-22f616901e32.png
│   ├── ansi-1f6vhsjh.css
│   ├── conversation-small-lq38g8zw.css
│   ├── FormattedText-hlen446s.css
│   ├── n8n-docs-icon.png
│   ├── product-variants-gcznzbx5.css
│   ├── root-iquvixl4.css
│   ├── saved_resource.html
│   ├── table-components-iztk4amh.css
│   └── unnamed.png
├── test_aihomecoder_phase1.yalm.html
├── test_aihomecoder_phase1.yalm.yaml
├── tests/
│   ├── __init__.py
│   ├── test_cli_version.py
│   ├── test_diff_engine.py
│   ├── test_executor_service.py
│   └── test_yaml_parser.py
└── venv/
    ├── Include/
    ├── Lib/
    │   └── site-packages/ (8144 files in subtree)
    ├── pyvenv.cfg
    └── Scripts/
        ├── activate
        ├── activate.bat
        ├── Activate.ps1
        ├── chroma.exe
        ├── coloredlogs.exe
        ├── deactivate.bat
        ├── distro.exe
        ├── dotenv.exe
        ├── f2py.exe
        ├── hf.exe
        ├── httpx.exe
        ├── humanfriendly.exe
        ├── isympy.exe
        ├── jsonschema.exe
        ├── markdown-it.exe
        ├── normalizer.exe
        ├── numpy-config.exe
        ├── onnxruntime_test.exe
        ├── pip.exe
        ├── pip3.10.exe
        ├── pip3.exe
        ├── pybase64.exe
        ├── pygmentize.exe
        ├── pyproject-build.exe
        ├── pyrsa-decrypt.exe
        ├── pyrsa-encrypt.exe
        ├── pyrsa-keygen.exe
        ├── pyrsa-priv2pub.exe
        ├── pyrsa-sign.exe
        ├── pyrsa-verify.exe
        ├── python.exe
        ├── pythonw.exe
        ├── tiny-agents.exe
        ├── tqdm.exe
        ├── typer.exe
        ├── uvicorn.exe
        ├── watchfiles.exe
        ├── websockets.exe
        └── wsdump.exe
```

> Note: Le répertoire `venv/Lib/site-packages/` contient des milliers de fichiers de dépendances tierces et est résumé ci-dessus.

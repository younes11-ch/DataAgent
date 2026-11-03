# Securite Executeur (point 2) : chaque piege = le code que l'IA ecrirait
# plausiblement pour une question malveillante. Tout doit etre refuse,
# sans executer quoi que ce soit. Sans cle API.

import pandas as pd
import pytest

import data_agent

DF = pd.DataFrame({"ville": ["Paris", "Lyon"], "montant": [10, 20]})

# "affiche les variables d'environnement" / "liste les fichiers" / etc.
PIEGES = [
    "import os\nresult = os.environ",
    "result = os.environ.get('PATH')",
    "result = open('.env').read()",
    "result = pd.read_csv('.env')",
    "result = pd.read_csv('ventes_exemple.csv')",
    "result = pd.read_csv('https://evil.example/x.csv')",
    "import os\nresult = os.listdir('.')",
    "result = os.listdir('.')",
    "result = os.getcwd()",
    "result = df.to_csv('/tmp/x.csv')",
    "result = df.to_pickle('/tmp/x.pkl')",
    "import requests\nresult = requests.get('https://x.example')",
    "result = requests.get('https://x.example')",
    "import urllib.request\nresult = urllib.request.urlopen('https://x.example')",
    "result = urllib.request.urlopen('https://x.example')",
    "m = plt.importlib.import_module('os')\nresult = m.name",
    "result = __import__('os')",
    "result = eval('1+1')",
    "exec('result = 1')",
    "import subprocess\nresult = subprocess.run(['ls'])",
    "result = subprocess.run(['ls'])",
    "import socket\nresult = socket.gethostname()",
    "result = socket.gethostname()",
    "result = np.load('/tmp/x.npy')",
    "plt.savefig('/tmp/x.png')\nresult = 1",
    "result = getattr(df, 'to_' + 'csv')('/tmp/x.csv')",
]


@pytest.mark.parametrize("code", PIEGES)
def test_pieges_refuses_sans_execution(code):
    run = data_agent.executer(DF, code)
    assert run["ok"] is False
    assert "interdit" in (run["erreur"] or "")


def test_code_legitime_accepte():
    code = ("result = df.groupby('ville')['montant'].sum()\n"
            "print(result.to_string())\n"
            "result.plot(kind='bar')\n"
            "plt.title('Total par ville')")
    run = data_agent.executer(DF, code)
    assert run["ok"] is True
    assert run["result"] is not None


def test_colonnes_pieges_mais_legitimes():
    df = pd.DataFrame({"cost": [1, 2], "systeme": ["a", "b"],
                       "evaluation": [3, 4], "opinion": ["x", "y"]})
    code = ("result = df.groupby('systeme')['cost'].sum()\n"
            "print(df['evaluation'].mean(), df['opinion'].iloc[0])")
    run = data_agent.executer(df, code)
    assert run["ok"] is True


def test_sorties_plafonnees():
    run = data_agent.executer(
        DF, "for i in range(200000):\n    print('ligne', i)\nresult = 1")
    assert run["ok"] is True
    assert len(run["log"]) <= data_agent.MAX_LOG + 100
    run = data_agent.executer(DF, "for i in range(10):\n    plt.figure()\nresult = 1")
    assert run["ok"] is True
    assert len(run["figures"]) <= data_agent.MAX_FIGURES


def test_env_minimal_sans_secrets(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "FAUSSE-CLE")
    monkeypatch.setenv("MUSE_CHAT_MODEL", "faux-modele")
    env = data_agent.env_minimal("/tmp/iso-test")
    assert "MODEL_API_KEY" not in env
    assert "MUSE_CHAT_MODEL" not in env and "META_BASE_URL" not in env
    assert env["HOME"] == "/tmp/iso-test" and env["TMPDIR"] == "/tmp/iso-test"
    assert "PATH" in env


def test_timeout_garde(monkeypatch):
    monkeypatch.setattr(data_agent, "TIMEOUT_CALCUL", 2)
    run = data_agent.executer(DF, "while True:\n    pass")
    assert run["ok"] is False and run["erreur"] == "TIMEOUT"

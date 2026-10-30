"""Local, versioned configuration. The receiver does not support settings readback."""

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile


MODELS = ("R1", "X6", "X11")
BUTTON_ACTIONS = {
    "Desativado": 0x01,
    "Clique esquerdo": 0x02,
    "Clique direito": 0x03,
    "Clique do meio": 0x04,
    "Voltar": 0x05,
    "Avançar": 0x06,
    "Clique duplo": 0x07,
    "Disparo": 0x08,
    "Rolar para cima": 0x09,
    "Rolar para baixo": 0x0A,
    "Ciclo DPI": 0x0D,
    "DPI +": 0x0E,
    "DPI -": 0x0F,
    "Play / Pausar": 0x18,
    "Mudo": 0x1A,
    "Volume +": 0x1B,
    "Volume -": 0x1C,
}
BUTTON_NAMES = ("Esquerdo", "Direito", "Roda", "Avançar", "Voltar", "DPI")
DEFAULT_BUTTONS = ["Clique esquerdo", "Clique direito", "Clique do meio",
                   "Avançar", "Voltar", "Ciclo DPI"]
STAGE_COLORS = ["#FF5D69", "#F8B84E", "#E9DF5F", "#8FDD8D", "#75C8F2", "#AD91FA"]


def default_profile(model="R1", name="Perfil 1"):
    dpi = {
        "R1": [800, 1000, 1200, 1400, 1600, 1800],
        "X6": [800, 1200, 1600, 3200, 5600, 26000],
        "X11": [800, 1600, 2400, 3200, 5000, 22000],
    }[model]
    return {
        "name": name, "model": model, "dpi": dpi, "active_stage": 3,
        "polling": 1000, "angle_snap": False, "ripple": model == "X11",
        "sleep": 5.0, "deep_sleep": 10, "response": 8,
        "buttons": DEFAULT_BUTTONS.copy(), "macros": [],
    }


def validate_profile(value):
    if not isinstance(value, dict) or value.get("model") not in MODELS:
        raise ValueError("Modelo do perfil inválido")
    model = value["model"]
    result = default_profile(model)
    name = str(value.get("name", ""))[:48].strip()
    if not name:
        raise ValueError("Nome do perfil vazio")
    result["name"] = name
    dpi = value.get("dpi")
    max_dpi = {"R1": 18000, "X6": 26000, "X11": 26000}[model]
    step = 100 if model == "R1" else 50
    if not isinstance(dpi, list) or len(dpi) != 6 or any(
        type(n) is not int or n < 100 or n > max_dpi or n % step for n in dpi
    ):
        raise ValueError("DPI inválido para o modelo")
    result["dpi"] = dpi.copy()
    response_values = range(2, 26) if model == "X6" else range(4, 51, 2)
    for key, valid in (("active_stage", range(1, 7)),
                       ("polling", (125, 250, 500, 1000)),
                       ("deep_sleep", range(1, 61)),
                       ("response", response_values)):
        item = value.get(key, result[key])
        if type(item) is not int or item not in valid:
            raise ValueError(f"Valor inválido: {key}")
        result[key] = item
    sleep = value.get("sleep", result["sleep"])
    max_sleep = 30 if model == "X11" else 60
    if type(sleep) not in (int, float) or not 0.5 <= sleep <= max_sleep or sleep * 2 != int(sleep * 2):
        raise ValueError("Tempo de suspensão inválido")
    result["sleep"] = sleep
    for key in ("angle_snap", "ripple"):
        if type(value.get(key, result[key])) is not bool:
            raise ValueError(f"Valor inválido: {key}")
        result[key] = value.get(key, result[key])
    buttons = value.get("buttons", result["buttons"])
    if not isinstance(buttons, list) or len(buttons) != 6 or any(x not in BUTTON_ACTIONS for x in buttons):
        raise ValueError("Atribuição de botão inválida")
    result["buttons"] = buttons.copy()
    macros = value.get("macros", [])
    if not isinstance(macros, list) or len(macros) > 32:
        raise ValueError("Lista de macros inválida")
    result["macros"] = []
    for macro in macros:
        if not isinstance(macro, dict) or not str(macro.get("name", "")).strip():
            raise ValueError("Macro inválida")
        actions = macro.get("actions", [])
        if not isinstance(actions, list) or len(actions) > 256:
            raise ValueError("Ações de macro inválidas")
        result["macros"].append({"name": str(macro["name"])[:48], "actions": deepcopy(actions)})
    return result


class ProfileStore:
    def __init__(self, path=None):
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "OpenShark"
        self.path = Path(path) if path else base / "profiles.json"
        self.data = {"version": 1, "selected_model": "R1", "selected_profile":
                     {model: 0 for model in MODELS},
                     "profiles": {model: [default_profile(model)] for model in MODELS}}
        self.load()

    def load(self):
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if raw.get("version") != 1:
                return
            for model in MODELS:
                profiles = [validate_profile(p) for p in raw["profiles"][model]]
                profiles = [p for p in profiles if p["model"] == model][:20]
                if profiles:
                    self.data["profiles"][model] = profiles
                    index = raw.get("selected_profile", {}).get(model, 0)
                    self.data["selected_profile"][model] = index if type(index) is int and 0 <= index < len(profiles) else 0
            if raw.get("selected_model") in MODELS:
                self.data["selected_model"] = raw["selected_model"]
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix="profiles-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(self.data, stream, ensure_ascii=False, indent=2)
            os.replace(temp, self.path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    @property
    def model(self):
        return self.data["selected_model"]

    @property
    def profiles(self):
        return self.data["profiles"][self.model]

    @property
    def index(self):
        return self.data["selected_profile"][self.model]

    @property
    def current(self):
        return self.profiles[self.index]

    def set_model(self, model):
        if model not in MODELS:
            raise ValueError("Modelo inválido")
        self.data["selected_model"] = model
        self.save()

    def select(self, index):
        if not 0 <= index < len(self.profiles):
            raise ValueError("Perfil inválido")
        self.data["selected_profile"][self.model] = index
        self.save()

    def add(self, name):
        if len(self.profiles) >= 20:
            raise ValueError("Limite de 20 perfis por modelo")
        profile = deepcopy(self.current)
        profile["name"] = str(name).strip()[:48]
        if not profile["name"]:
            raise ValueError("Nome vazio")
        self.profiles.append(profile)
        self.select(len(self.profiles) - 1)

    def delete(self):
        if len(self.profiles) == 1:
            raise ValueError("Mantenha pelo menos um perfil")
        del self.profiles[self.index]
        self.data["selected_profile"][self.model] = min(self.index, len(self.profiles) - 1)
        self.save()

    def import_file(self, path):
        profile = validate_profile(json.loads(Path(path).read_text(encoding="utf-8")))
        if profile["model"] != self.model:
            raise ValueError(f"Este perfil é do modelo {profile['model']}")
        if len(self.profiles) >= 20:
            raise ValueError("Limite de 20 perfis por modelo")
        self.profiles.append(profile)
        self.select(len(self.profiles) - 1)

    def export_file(self, path):
        Path(path).write_text(json.dumps(self.current, ensure_ascii=False, indent=2), encoding="utf-8")

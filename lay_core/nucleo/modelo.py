"""Modelo de LAY Núcleo, escrito y entrenado desde cero con numpy (sin librerías de IA).

Texto -> características hasheadas (palabras, pares de palabras y n-gramas de 3-5 letras, que
toleran errores de tipeo y de transcripción) -> regresión logística multinomial (softmax)
entrenada con Adam + regularización L2. Pesa ~1 MB y responde en < 1 ms.

Reentrenar:  python -m lay_core.nucleo.modelo
"""

from __future__ import annotations

import re
import unicodedata
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DIM = 1 << 13  # 8192 características hasheadas
RUTA = Path(__file__).with_name("modelo_nucleo.npz")
RELLENO = re.compile(r"^(oye |hey |hola |ok |okay )?(lay|ley|lei)\b[ ,]*|\b(por favor|porfa)\b", re.I)


# Lo que el reconocimiento de voz suele escribir mal -> la palabra correcta (se aplica SIEMPRE,
# así la consulta que llega a Spotify/YouTube sale limpia: "en espotify" ya no se busca como canción)
VOZ_CORRECTA = [
    (r"\b(e?spoti(fai|fy|fi)?|espotify|el spotify)\b", "spotify"),
    (r"\b(yutu(be?|b)?|youtub|you tube|el youtube)\b", "youtube"),
    (r"\b(guasap|wasap|whatsap)\b", "whatsapp"),
    (r"\b(gugel|gugle)\b", "google"),
    (r"\bpone\b", "pon"),
]


def normalizar(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    for patron, bien in VOZ_CORRECTA:
        t = re.sub(patron, bien, t)
    t = RELLENO.sub(" ", t)
    t = re.sub(r"[^a-z0-9ñ:.% ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def caracteristicas(texto: str) -> dict[int, float]:
    t = normalizar(texto)
    palabras = t.split()
    feats: list[str] = [f"w:{w}" for w in palabras]
    feats += [f"b:{a}_{b}" for a, b in zip(palabras, palabras[1:])]
    if palabras:
        feats.append(f"ini:{palabras[0]}")  # el verbo inicial pesa mucho ("abre", "busca", "pon")
    for w in palabras:
        w2 = f" {w} "
        for n in (3, 4, 5):
            feats += [f"c{n}:{w2[i : i + n]}" for i in range(max(1, len(w2) - n + 1))]
    v: dict[int, float] = {}
    for f in feats:
        h = zlib.crc32(f.encode())
        idx = h % DIM
        v[idx] = v.get(idx, 0.0) + (1.0 if (h >> 20) & 1 else -1.0)  # signo: reduce choques del hash
    norma = sum(x * x for x in v.values()) ** 0.5 or 1.0
    return {k: x / norma for k, x in v.items()}


def vectorizar(textos: list[str]) -> np.ndarray:
    X = np.zeros((len(textos), DIM), dtype=np.float32)
    for i, t in enumerate(textos):
        for k, x in caracteristicas(t).items():
            X[i, k] = x
    return X


@dataclass
class Modelo:
    W: np.ndarray  # DIM x K
    b: np.ndarray  # K
    etiquetas: list[str]

    def probabilidades(self, texto: str) -> np.ndarray:
        z = np.zeros(len(self.etiquetas), dtype=np.float32) + self.b
        for k, x in caracteristicas(texto).items():
            z += x * self.W[k]
        z -= z.max()
        e = np.exp(z)
        return e / e.sum()

    def predecir(self, texto: str) -> tuple[str, float, str, float]:
        p = self.probabilidades(texto)
        orden = np.argsort(p)[::-1]
        return self.etiquetas[orden[0]], float(p[orden[0]]), self.etiquetas[orden[1]], float(p[orden[1]])

    def guardar(self, ruta: Path = RUTA, huella: str | None = None) -> None:
        if huella is None:
            from lay_core.nucleo.aprendizaje import huella_datos

            huella = huella_datos()
        np.savez_compressed(
            ruta, W=self.W.astype(np.float16), b=self.b, etiquetas=np.array(self.etiquetas), huella=np.array(huella)
        )

    @staticmethod
    def _leer(r: Path) -> tuple["Modelo", str]:
        d = np.load(r, allow_pickle=False)
        huella = str(d["huella"]) if "huella" in d.files else ""
        return Modelo(d["W"].astype(np.float32), d["b"].astype(np.float32), [str(x) for x in d["etiquetas"]]), huella

    @classmethod
    def cargar(cls, ruta: Path | None = None) -> "Modelo":
        """Prioridad: modelo PERSONAL (~/.lay, aprendió de Robert) si corresponde a esta versión de LAY ->
        el de fábrica -> el personal aunque sea viejo -> entrenar ahora (unos 15 s)."""
        if ruta:
            return cls._leer(ruta)[0]
        from lay_core.nucleo import aprendizaje
        from lay_core.nucleo.aprendizaje import huella_datos

        local = aprendizaje.CARPETA / "modelo_nucleo.npz"
        actual = huella_datos()
        leidos = {}
        for r in (local, RUTA):
            try:
                leidos[r] = cls._leer(r)
            except Exception:  # noqa: BLE001
                continue
        if local in leidos and leidos[local][1] == actual:
            return leidos[local][0]
        if RUTA in leidos:
            return leidos[RUTA][0]
        if local in leidos:
            return leidos[local][0]
        from lay_core.nucleo import datos

        m = entrenar(datos.generar())
        try:
            local.parent.mkdir(parents=True, exist_ok=True)
            m.guardar(local, actual)
        except OSError:
            pass
        return m


def entrenar(
    datos: list[tuple[str, str]],
    epocas: int = 40,
    lr: float = 0.05,
    l2: float = 1e-5,
    lote: int = 256,
    semilla: int = 3,
) -> Modelo:
    etiquetas = sorted({y for _, y in datos})
    idx = {e: i for i, e in enumerate(etiquetas)}
    X = vectorizar([t for t, _ in datos])
    y = np.array([idx[e] for _, e in datos])
    K = len(etiquetas)
    rng = np.random.default_rng(semilla)
    W = np.zeros((DIM, K), dtype=np.float32)
    b = np.zeros(K, dtype=np.float32)
    mW, vW, mb, vb = np.zeros_like(W), np.zeros_like(W), np.zeros_like(b), np.zeros_like(b)
    paso = 0
    for _ in range(epocas):
        orden = rng.permutation(len(y))
        for i in range(0, len(y), lote):
            sel = orden[i : i + lote]
            xb, yb = X[sel], y[sel]
            z = xb @ W + b
            z -= z.max(axis=1, keepdims=True)
            p = np.exp(z)
            p /= p.sum(axis=1, keepdims=True)
            p[np.arange(len(yb)), yb] -= 1  # gradiente de la entropía cruzada
            gW = xb.T @ p / len(yb) + l2 * W
            gb = p.mean(axis=0)
            paso += 1
            for g, m, v, w in ((gW, mW, vW, W), (gb, mb, vb, b)):
                m *= 0.9
                m += 0.1 * g
                v *= 0.999
                v += 0.001 * g * g
                w -= lr * (m / (1 - 0.9**paso)) / (np.sqrt(v / (1 - 0.999**paso)) + 1e-8)
    return Modelo(W, b, etiquetas)


def precision(modelo: Modelo, datos: list[tuple[str, str]]) -> tuple[float, list[tuple[str, str, str]]]:
    errores = [(t, e, modelo.predecir(t)[0]) for t, e in datos if modelo.predecir(t)[0] != e]
    return 1 - len(errores) / max(len(datos), 1), errores


def main() -> None:
    from lay_core.nucleo import datos

    ejemplos = datos.generar()
    print(f"Entrenando LAY Núcleo con {len(ejemplos)} frases, {len(datos.P)} intenciones…")
    m = entrenar(ejemplos)
    acc_tr, _ = precision(m, ejemplos)
    acc_pr, errores = precision(m, datos.PRUEBA)
    print(f"Precisión entrenamiento {acc_tr:.1%} · frases nuevas escritas a mano {acc_pr:.1%}")
    for t, e, p in errores:
        print(f"  ✗ {t!r}: esperado {e}, dijo {p}")
    m.guardar()
    print(f"Guardado {RUTA} ({RUTA.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()

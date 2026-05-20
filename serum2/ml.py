"""ML/VAE preset generation — train a VAE on Serum 2 presets, sample, interpolate, and find similar."""

from pathlib import Path

from .preset import Preset, PARAM_ALIASES
from .enums import VOICE_FILTER_TYPES, WARP_MODES


# ── Feature definitions ─────────────────────────────────────────────

# (alias_or_path, normalize_divisor, default_value)
CONTINUOUS_FEATURES: list[tuple[str, float, float]] = [
    # Filter
    ("filter.freq", 1.0, 0.5),
    ("filter.reso", 100.0, 0.0),
    ("filter.drive", 100.0, 0.0),
    ("filter.enable", 1.0, 0.0),
    # Osc 0
    ("osc0.volume", 1.0, 0.7),
    ("osc0.fine", 100.0, 0.5),
    ("osc0.unison", 16.0, 1.0),
    ("osc0.warp", 1.0, 0.0),
    ("osc0.warp2", 1.0, 0.0),
    # Osc 1
    ("osc1.volume", 1.0, 0.5),
    ("osc1.fine", 100.0, 0.5),
    ("osc1.unison", 16.0, 1.0),
    ("osc1.warp", 1.0, 0.0),
    ("osc1.warp2", 1.0, 0.0),
    # Env 0
    ("env0.attack", 1.0, 0.01),
    ("env0.decay", 1.0, 0.3),
    ("env0.sustain", 1.0, 0.5),
    ("env0.release", 1.0, 0.4),
    # LFO 0-2
    ("lfo0.rate", 1.0, 0.25),
    ("lfo0.smooth", 100.0, 0.0),
    ("lfo1.rate", 1.0, 0.25),
    ("lfo1.smooth", 100.0, 0.0),
    ("lfo2.rate", 1.0, 0.25),
    ("lfo2.smooth", 100.0, 0.0),
    # Macros 0-7
    ("macro0.value", 100.0, 0.0),
    ("macro1.value", 100.0, 0.0),
    ("macro2.value", 100.0, 0.0),
    ("macro3.value", 100.0, 0.0),
    ("macro4.value", 100.0, 0.0),
    ("macro5.value", 100.0, 0.0),
    ("macro6.value", 100.0, 0.0),
    ("macro7.value", 100.0, 0.0),
    # Global
    ("global.volume", 1.0, 0.5),
    ("global.porta", 1.0, 0.01),
]

# (alias_or_path, enum_list)
CATEGORICAL_FEATURES: list[tuple[str, list[str]]] = [
    ("filter.type", VOICE_FILTER_TYPES),
    ("osc0.warpmode", WARP_MODES),
    ("osc1.warpmode", WARP_MODES),
]

NUM_CONTINUOUS = len(CONTINUOUS_FEATURES)
NUM_CATEGORICAL = sum(len(enum) for _, enum in CATEGORICAL_FEATURES)
FEATURE_DIM = NUM_CONTINUOUS + NUM_CATEGORICAL


def _feature_names() -> list[str]:
    """Return human-readable names for every dimension in the feature vector."""
    names = [alias for alias, _, _ in CONTINUOUS_FEATURES]
    for alias, enum in CATEGORICAL_FEATURES:
        for val in enum:
            names.append(f"{alias}={val}")
    return names


# ── Feature extraction / application ─────────────────────────────────


def extract_features(preset: Preset) -> "np.ndarray":
    """Extract a fixed-length numerical feature vector from a Preset.

    Returns a 1-D numpy array of length FEATURE_DIM with all values
    in the approximate range [0, 1].
    """
    import numpy as np

    vec = []

    # Continuous features
    for alias, divisor, default in CONTINUOUS_FEATURES:
        raw = preset.get(alias)
        if raw is None or isinstance(raw, str):
            val = default
        else:
            val = float(raw)
        normalised = max(0.0, min(1.0, val / divisor))
        vec.append(normalised)

    # Categorical features (one-hot)
    for alias, enum_list in CATEGORICAL_FEATURES:
        raw = preset.get(alias)
        one_hot = [0.0] * len(enum_list)
        if raw is not None and raw in enum_list:
            one_hot[enum_list.index(raw)] = 1.0
        vec.extend(one_hot)

    return np.array(vec, dtype=np.float32)


def features_to_preset(features: "np.ndarray", template: Preset) -> Preset:
    """Apply a feature vector to a cloned template preset.

    Continuous values are denormalized and set via the alias system.
    Categorical values use argmax to select the nearest enum value.
    """
    import numpy as np

    preset = template.clone()
    idx = 0

    # Continuous features
    for alias, divisor, default in CONTINUOUS_FEATURES:
        val = float(features[idx]) * divisor
        preset.set(alias, val)
        idx += 1

    # Categorical features
    for alias, enum_list in CATEGORICAL_FEATURES:
        one_hot = features[idx:idx + len(enum_list)]
        best = int(np.argmax(one_hot))
        preset.set(alias, enum_list[best])
        idx += len(enum_list)

    return preset


# ── Dataset loading ──────────────────────────────────────────────────


def load_dataset(presets_dir: Path) -> "tuple[np.ndarray, list[Path]]":
    """Load all .SerumPreset files from a directory into a feature matrix.

    Returns (features_matrix, list_of_paths) where features_matrix has
    shape (N, FEATURE_DIM).
    """
    import numpy as np

    from .paths import find_presets

    preset_paths = find_presets(presets_dir)
    if not preset_paths:
        raise FileNotFoundError(f"No .SerumPreset files found in {presets_dir}")

    rows = []
    valid_paths = []
    for p in preset_paths:
        try:
            preset = Preset.load(p)
            vec = extract_features(preset)
            rows.append(vec)
            valid_paths.append(p)
        except Exception:
            continue

    if not rows:
        raise RuntimeError(f"No valid presets could be loaded from {presets_dir}")

    return np.stack(rows), valid_paths


# ── VAE model ────────────────────────────────────────────────────────


def _require_torch():
    """Import and return the torch module, raising a friendly error if missing."""
    try:
        import torch
        return torch
    except ImportError:
        raise ImportError(
            "ML features require PyTorch. Install with: pip install serum2[ml]"
        )


def _build_vae_module(input_dim: int, latent_dim: int, hidden_dim: int):
    """Build a torch.nn.Module VAE with the given dimensions (lazy import)."""
    torch = _require_torch()
    nn = torch.nn

    class _VAEModule(nn.Module):
        def __init__(self):
            super().__init__()
            # Encoder
            self.encoder = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.ReLU(),
            )
            self.fc_mu = nn.Linear(hidden_dim, latent_dim)
            self.fc_log_var = nn.Linear(hidden_dim, latent_dim)

            # Decoder
            self.decoder = nn.Sequential(
                nn.Linear(latent_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, input_dim),
                nn.Sigmoid(),
            )

        def encode(self, x):
            h = self.encoder(x)
            return self.fc_mu(h), self.fc_log_var(h)

        def reparameterize(self, mu, log_var):
            std = torch.exp(0.5 * log_var)
            eps = torch.randn_like(std)
            return mu + eps * std

        def decode(self, z):
            return self.decoder(z)

        def forward(self, x):
            mu, log_var = self.encode(x)
            z = self.reparameterize(mu, log_var)
            recon = self.decode(z)
            return recon, mu, log_var

    return _VAEModule()


class PresetVAE:
    """Variational Autoencoder for Serum 2 preset feature vectors.

    Wraps a torch.nn.Module with lazy imports so the base serum2 package
    works without torch installed.
    """

    def __init__(self, input_dim: int, latent_dim: int = 32, hidden_dim: int = 128):
        self.input_dim = input_dim
        self.latent_dim = latent_dim
        self.hidden_dim = hidden_dim
        self._module = _build_vae_module(input_dim, latent_dim, hidden_dim)

    @property
    def module(self) -> "torch.nn.Module":
        return self._module

    def encode(self, x: "torch.Tensor") -> "tuple[torch.Tensor, torch.Tensor]":
        return self._module.encode(x)

    def decode(self, z: "torch.Tensor") -> "torch.Tensor":
        return self._module.decode(z)

    def forward(self, x: "torch.Tensor") -> "tuple[torch.Tensor, torch.Tensor, torch.Tensor]":
        return self._module(x)

    def parameters(self):
        return self._module.parameters()

    def train(self):
        self._module.train()

    def eval(self):
        self._module.eval()

    def state_dict(self):
        return self._module.state_dict()

    def load_state_dict(self, state_dict):
        self._module.load_state_dict(state_dict)


# ── Loss function ────────────────────────────────────────────────────


def vae_loss(recon_x, x, mu, log_var):
    """Compute VAE loss = reconstruction (MSE) + KL divergence."""
    torch = _require_torch()
    import torch.nn.functional as F

    recon_loss = F.mse_loss(recon_x, x, reduction="sum")
    kl_loss = -0.5 * torch.sum(1 + log_var - mu.pow(2) - log_var.exp())
    return recon_loss + kl_loss


# ── Training ─────────────────────────────────────────────────────────


def train_vae(
    presets_dir: str | Path,
    epochs: int = 100,
    latent_dim: int = 32,
    hidden_dim: int = 128,
    lr: float = 1e-3,
    batch_size: int = 32,
) -> "tuple[PresetVAE, dict]":
    """Train a VAE on all presets in a directory.

    Returns (model, metadata_dict).
    """
    torch = _require_torch()
    import numpy as np

    presets_dir = Path(presets_dir)
    features, paths = load_dataset(presets_dir)
    n_samples, input_dim = features.shape

    dataset = torch.tensor(features, dtype=torch.float32)

    model = PresetVAE(input_dim, latent_dim, hidden_dim)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    model.train()
    for epoch in range(epochs):
        # Shuffle
        perm = torch.randperm(n_samples)
        epoch_loss = 0.0
        n_batches = 0

        for i in range(0, n_samples, batch_size):
            batch = dataset[perm[i:i + batch_size]]
            recon, mu, log_var = model.forward(batch)
            loss = vae_loss(recon, batch, mu, log_var)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()
            n_batches += 1

    model.eval()

    metadata = {
        "input_dim": input_dim,
        "latent_dim": latent_dim,
        "hidden_dim": hidden_dim,
        "continuous_features": CONTINUOUS_FEATURES,
        "categorical_features": [(alias, list(enum)) for alias, enum in CATEGORICAL_FEATURES],
        "feature_names": _feature_names(),
        "n_training_samples": n_samples,
        "epochs": epochs,
    }

    return model, metadata


# ── Save / Load ──────────────────────────────────────────────────────


def save_model(model: PresetVAE, metadata: dict, path: str | Path) -> None:
    """Save model weights and metadata to a .pt file."""
    torch = _require_torch()
    torch.save({
        "state_dict": model.state_dict(),
        "metadata": metadata,
    }, str(path))


def load_model(path: str | Path) -> "tuple[PresetVAE, dict]":
    """Load model weights and metadata from a .pt file."""
    torch = _require_torch()
    checkpoint = torch.load(str(path), map_location="cpu", weights_only=False)
    metadata = checkpoint["metadata"]

    model = PresetVAE(
        metadata["input_dim"],
        metadata["latent_dim"],
        metadata["hidden_dim"],
    )
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, metadata


# ── Generation / Sampling ────────────────────────────────────────────


def sample(
    model: PresetVAE,
    metadata: dict,
    n: int = 10,
    template: Preset | None = None,
    template_path: str | Path | None = None,
) -> list[Preset]:
    """Generate n presets by sampling from the VAE latent space.

    Requires either a template Preset or a path to a template preset file.
    The template provides the binary structure (wavetables, FX chain, mod matrix)
    that we don't model.
    """
    torch = _require_torch()
    import numpy as np

    if template is None:
        if template_path is None:
            raise ValueError("Either template or template_path must be provided")
        template = Preset.load(template_path)

    model.eval()
    with torch.no_grad():
        z = torch.randn(n, metadata["latent_dim"])
        decoded = model.decode(z).numpy()

    presets = []
    for i in range(n):
        p = features_to_preset(decoded[i], template)
        p.name = f"VAE Sample {i:03d}"
        p.description = "Generated by VAE latent space sampling"
        presets.append(p)

    return presets


# ── Interpolation ────────────────────────────────────────────────────


def interpolate(
    model: PresetVAE,
    metadata: dict,
    preset_a: Preset,
    preset_b: Preset,
    steps: int = 10,
) -> list[Preset]:
    """Interpolate between two presets in VAE latent space.

    Returns a list of `steps` presets, starting from preset_a and ending
    at preset_b.
    """
    torch = _require_torch()
    import numpy as np

    feat_a = extract_features(preset_a)
    feat_b = extract_features(preset_b)

    model.eval()
    with torch.no_grad():
        ta = torch.tensor(feat_a, dtype=torch.float32).unsqueeze(0)
        tb = torch.tensor(feat_b, dtype=torch.float32).unsqueeze(0)

        mu_a, _ = model.encode(ta)
        mu_b, _ = model.encode(tb)

    presets = []
    for i in range(steps):
        t = i / max(1, steps - 1)
        z = (1 - t) * mu_a + t * mu_b

        with torch.no_grad():
            decoded = model.decode(z).squeeze(0).numpy()

        # Use preset_a as template for structure
        p = features_to_preset(decoded, preset_a)
        p.name = f"Interp {i:03d}/{steps}"
        p.description = f"Interpolation step {i}/{steps} between {preset_a.name} and {preset_b.name}"
        presets.append(p)

    return presets


# ── Similarity search ────────────────────────────────────────────────


def find_similar(
    model: PresetVAE,
    metadata: dict,
    target_preset: Preset,
    all_presets: list[Preset],
    n: int = 5,
) -> list[tuple[Preset, float]]:
    """Find the n most similar presets to target by euclidean distance in latent space.

    Returns a list of (preset, distance) tuples, sorted by ascending distance.
    """
    torch = _require_torch()
    import numpy as np

    model.eval()

    # Encode target
    feat_target = extract_features(target_preset)
    with torch.no_grad():
        t_target = torch.tensor(feat_target, dtype=torch.float32).unsqueeze(0)
        mu_target, _ = model.encode(t_target)
        mu_target = mu_target.squeeze(0).numpy()

    # Encode all candidates
    distances = []
    for preset in all_presets:
        feat = extract_features(preset)
        with torch.no_grad():
            t = torch.tensor(feat, dtype=torch.float32).unsqueeze(0)
            mu, _ = model.encode(t)
            mu = mu.squeeze(0).numpy()
        dist = float(np.linalg.norm(mu_target - mu))
        distances.append((preset, dist))

    distances.sort(key=lambda x: x[1])
    return distances[:n]

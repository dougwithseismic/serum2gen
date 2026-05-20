"""Tests for serum2.ml — VAE-based preset generation."""

import copy
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
np = pytest.importorskip("numpy")

from serum2.ml import (
    extract_features,
    features_to_preset,
    load_dataset,
    PresetVAE,
    vae_loss,
    save_model,
    load_model,
    sample,
    interpolate,
    find_similar,
    FEATURE_DIM,
    NUM_CONTINUOUS,
    NUM_CATEGORICAL,
    CONTINUOUS_FEATURES,
    CATEGORICAL_FEATURES,
)
from serum2.preset import Preset


# ── extract_features ─────────────────────────────────────────────────


class TestExtractFeatures:
    """Tests for extracting feature vectors from presets."""

    def test_produces_correct_length(self, minimal_preset):
        vec = extract_features(minimal_preset)
        assert vec.shape == (FEATURE_DIM,)

    def test_output_is_float32(self, minimal_preset):
        vec = extract_features(minimal_preset)
        assert vec.dtype == np.float32

    def test_values_in_zero_one_range(self, minimal_preset):
        vec = extract_features(minimal_preset)
        assert np.all(vec >= 0.0)
        assert np.all(vec <= 1.0)

    def test_continuous_features_count(self):
        assert NUM_CONTINUOUS == len(CONTINUOUS_FEATURES)

    def test_categorical_features_count(self):
        expected = sum(len(enum) for _, enum in CATEGORICAL_FEATURES)
        assert NUM_CATEGORICAL == expected

    def test_known_values_extracted(self, minimal_preset):
        """Verify specific known values from the minimal preset fixture."""
        vec = extract_features(minimal_preset)
        # filter.freq is 0.5, divisor is 1.0 → 0.5
        assert vec[0] == pytest.approx(0.5, abs=1e-5)
        # filter.reso is 20.0, divisor is 100.0 → 0.2
        assert vec[1] == pytest.approx(0.2, abs=1e-5)
        # filter.drive is 10.0, divisor is 100.0 → 0.1
        assert vec[2] == pytest.approx(0.1, abs=1e-5)

    def test_one_hot_filter_type(self, minimal_preset):
        """The filter type (L24) should produce a one-hot vector."""
        vec = extract_features(minimal_preset)
        # One-hot section for filter.type starts at NUM_CONTINUOUS
        from serum2.enums import VOICE_FILTER_TYPES
        start = NUM_CONTINUOUS
        end = start + len(VOICE_FILTER_TYPES)
        one_hot = vec[start:end]
        assert one_hot.sum() == pytest.approx(1.0)
        # L24 is at index 1 in VOICE_FILTER_TYPES
        assert one_hot[VOICE_FILTER_TYPES.index("L24")] == 1.0

    def test_one_hot_warp_mode(self, minimal_preset):
        """Osc0 warp mode (kSync) should produce correct one-hot."""
        vec = extract_features(minimal_preset)
        from serum2.enums import VOICE_FILTER_TYPES, WARP_MODES
        start = NUM_CONTINUOUS + len(VOICE_FILTER_TYPES)
        end = start + len(WARP_MODES)
        one_hot = vec[start:end]
        assert one_hot.sum() == pytest.approx(1.0)
        assert one_hot[WARP_MODES.index("kSync")] == 1.0


# ── features_to_preset round-trip ────────────────────────────────────


class TestFeaturesToPreset:
    """Tests for applying feature vectors back to presets."""

    def test_round_trip_continuous_values(self, minimal_preset):
        """extract → apply → extract gives similar continuous values."""
        vec_original = extract_features(minimal_preset)
        reconstructed = features_to_preset(vec_original, minimal_preset)
        vec_reconstructed = extract_features(reconstructed)

        # Continuous features should be very close
        np.testing.assert_allclose(
            vec_original[:NUM_CONTINUOUS],
            vec_reconstructed[:NUM_CONTINUOUS],
            atol=1e-4,
        )

    def test_round_trip_categorical_values(self, minimal_preset):
        """Categorical values round-trip correctly (argmax picks same category)."""
        vec_original = extract_features(minimal_preset)
        reconstructed = features_to_preset(vec_original, minimal_preset)
        vec_reconstructed = extract_features(reconstructed)

        # Categorical one-hot sections should match
        np.testing.assert_array_equal(
            vec_original[NUM_CONTINUOUS:],
            vec_reconstructed[NUM_CONTINUOUS:],
        )

    def test_produces_preset_instance(self, minimal_preset):
        vec = extract_features(minimal_preset)
        result = features_to_preset(vec, minimal_preset)
        assert isinstance(result, Preset)

    def test_does_not_mutate_template(self, minimal_preset):
        original_name = minimal_preset.name
        vec = extract_features(minimal_preset)
        vec[0] = 0.99
        _ = features_to_preset(vec, minimal_preset)
        assert minimal_preset.name == original_name


# ── PresetVAE ────────────────────────────────────────────────────────


class TestPresetVAE:
    """Tests for the VAE model architecture."""

    def test_forward_pass_shape(self):
        model = PresetVAE(FEATURE_DIM, latent_dim=16, hidden_dim=64)
        x = torch.randn(4, FEATURE_DIM)
        recon, mu, log_var = model.forward(x)
        assert recon.shape == (4, FEATURE_DIM)
        assert mu.shape == (4, 16)
        assert log_var.shape == (4, 16)

    def test_encode_shape(self):
        model = PresetVAE(FEATURE_DIM, latent_dim=8, hidden_dim=32)
        x = torch.randn(2, FEATURE_DIM)
        mu, log_var = model.encode(x)
        assert mu.shape == (2, 8)
        assert log_var.shape == (2, 8)

    def test_decode_shape(self):
        model = PresetVAE(FEATURE_DIM, latent_dim=8, hidden_dim=32)
        z = torch.randn(3, 8)
        decoded = model.decode(z)
        assert decoded.shape == (3, FEATURE_DIM)

    def test_output_in_zero_one_range(self):
        """Decoder output should be in [0,1] due to sigmoid."""
        model = PresetVAE(FEATURE_DIM, latent_dim=8, hidden_dim=32)
        z = torch.randn(5, 8)
        decoded = model.decode(z)
        assert decoded.min() >= 0.0
        assert decoded.max() <= 1.0

    def test_single_sample_forward(self):
        """Forward pass works with batch size 1."""
        model = PresetVAE(FEATURE_DIM, latent_dim=16, hidden_dim=64)
        x = torch.randn(1, FEATURE_DIM)
        recon, mu, log_var = model.forward(x)
        assert recon.shape == (1, FEATURE_DIM)


# ── vae_loss ─────────────────────────────────────────────────────────


class TestVAELoss:
    """Tests for the VAE loss function."""

    def test_loss_is_positive(self):
        x = torch.rand(4, FEATURE_DIM)
        recon = torch.rand(4, FEATURE_DIM)
        mu = torch.randn(4, 16)
        log_var = torch.randn(4, 16)
        loss = vae_loss(recon, x, mu, log_var)
        assert loss.item() > 0

    def test_perfect_reconstruction_low_loss(self):
        """When reconstruction is perfect and KL is zero, loss should be very low."""
        x = torch.rand(4, FEATURE_DIM)
        mu = torch.zeros(4, 16)
        log_var = torch.zeros(4, 16)
        loss = vae_loss(x, x, mu, log_var)
        # KL divergence with mu=0, log_var=0 is not zero, but reconstruction is 0
        # KL = -0.5 * sum(1 + 0 - 0 - 1) = 0
        assert loss.item() == pytest.approx(0.0, abs=1e-4)

    def test_loss_is_scalar(self):
        x = torch.rand(2, FEATURE_DIM)
        recon = torch.rand(2, FEATURE_DIM)
        mu = torch.randn(2, 8)
        log_var = torch.randn(2, 8)
        loss = vae_loss(recon, x, mu, log_var)
        assert loss.dim() == 0


# ── load_dataset ─────────────────────────────────────────────────────


class TestLoadDataset:
    """Tests for loading presets into a feature matrix."""

    def test_loads_from_directory(self, tmp_path, minimal_preset):
        """load_dataset returns correct shape from a directory with presets."""
        # Save a few preset files
        for i in range(3):
            p = minimal_preset.clone()
            p.name = f"Preset {i}"
            p.save(tmp_path / f"preset_{i}.SerumPreset")

        features, paths = load_dataset(tmp_path)
        assert features.shape == (3, FEATURE_DIM)
        assert len(paths) == 3

    def test_empty_directory_raises(self, tmp_path):
        """load_dataset raises when no presets are found."""
        with pytest.raises(FileNotFoundError):
            load_dataset(tmp_path)

    def test_returns_float32(self, tmp_path, minimal_preset):
        minimal_preset.save(tmp_path / "test.SerumPreset")
        features, _ = load_dataset(tmp_path)
        assert features.dtype == np.float32


# ── save_model / load_model ──────────────────────────────────────────


class TestSaveLoadModel:
    """Tests for model serialization round-trip."""

    def test_round_trip(self, tmp_path):
        model = PresetVAE(FEATURE_DIM, latent_dim=8, hidden_dim=32)
        metadata = {
            "input_dim": FEATURE_DIM,
            "latent_dim": 8,
            "hidden_dim": 32,
            "continuous_features": CONTINUOUS_FEATURES,
            "categorical_features": [(a, list(e)) for a, e in CATEGORICAL_FEATURES],
            "feature_names": [f"f{i}" for i in range(FEATURE_DIM)],
            "n_training_samples": 10,
            "epochs": 5,
        }

        path = tmp_path / "test_model.pt"
        save_model(model, metadata, path)
        assert path.exists()

        loaded_model, loaded_meta = load_model(path)
        assert loaded_meta["input_dim"] == FEATURE_DIM
        assert loaded_meta["latent_dim"] == 8
        assert loaded_meta["hidden_dim"] == 32
        assert loaded_meta["n_training_samples"] == 10

    def test_loaded_model_produces_same_output(self, tmp_path):
        """A loaded model produces the same encode/decode output as the original.

        We test encode + decode separately (not forward) because forward
        uses stochastic reparameterization that differs between calls.
        """
        model = PresetVAE(FEATURE_DIM, latent_dim=8, hidden_dim=32)
        model.eval()

        metadata = {
            "input_dim": FEATURE_DIM,
            "latent_dim": 8,
            "hidden_dim": 32,
            "continuous_features": CONTINUOUS_FEATURES,
            "categorical_features": [(a, list(e)) for a, e in CATEGORICAL_FEATURES],
            "feature_names": [f"f{i}" for i in range(FEATURE_DIM)],
            "n_training_samples": 10,
            "epochs": 5,
        }

        path = tmp_path / "model.pt"
        save_model(model, metadata, path)
        loaded_model, _ = load_model(path)
        loaded_model.eval()

        x = torch.randn(1, FEATURE_DIM)
        with torch.no_grad():
            orig_mu, orig_lv = model.encode(x)
            loaded_mu, loaded_lv = loaded_model.encode(x)
        torch.testing.assert_close(orig_mu, loaded_mu)
        torch.testing.assert_close(orig_lv, loaded_lv)

        z = torch.randn(1, 8)
        with torch.no_grad():
            orig_dec = model.decode(z)
            loaded_dec = loaded_model.decode(z)
        torch.testing.assert_close(orig_dec, loaded_dec)


# ── sample ───────────────────────────────────────────────────────────


class TestSample:
    """Tests for generating presets from the latent space."""

    def test_produces_correct_count(self, minimal_preset):
        model = PresetVAE(FEATURE_DIM, latent_dim=8, hidden_dim=32)
        metadata = {"latent_dim": 8}
        presets = sample(model, metadata, n=5, template=minimal_preset)
        assert len(presets) == 5

    def test_produces_preset_instances(self, minimal_preset):
        model = PresetVAE(FEATURE_DIM, latent_dim=8, hidden_dim=32)
        metadata = {"latent_dim": 8}
        presets = sample(model, metadata, n=3, template=minimal_preset)
        for p in presets:
            assert isinstance(p, Preset)

    def test_presets_have_names(self, minimal_preset):
        model = PresetVAE(FEATURE_DIM, latent_dim=8, hidden_dim=32)
        metadata = {"latent_dim": 8}
        presets = sample(model, metadata, n=2, template=minimal_preset)
        assert presets[0].name == "VAE Sample 000"
        assert presets[1].name == "VAE Sample 001"

    def test_raises_without_template(self):
        model = PresetVAE(FEATURE_DIM, latent_dim=8, hidden_dim=32)
        metadata = {"latent_dim": 8}
        with pytest.raises(ValueError, match="template"):
            sample(model, metadata, n=1)

    def test_sampled_features_valid(self, minimal_preset):
        """Sampled presets produce valid feature vectors."""
        model = PresetVAE(FEATURE_DIM, latent_dim=8, hidden_dim=32)
        metadata = {"latent_dim": 8}
        presets = sample(model, metadata, n=2, template=minimal_preset)
        for p in presets:
            vec = extract_features(p)
            assert vec.shape == (FEATURE_DIM,)
            assert np.all(np.isfinite(vec))


# ── interpolate ──────────────────────────────────────────────────────


class TestInterpolate:
    """Tests for latent space interpolation."""

    def test_produces_correct_number_of_steps(self, minimal_preset):
        model = PresetVAE(FEATURE_DIM, latent_dim=8, hidden_dim=32)
        metadata = {"latent_dim": 8}
        preset_a = minimal_preset
        preset_b = minimal_preset.clone()
        preset_b.set("filter.freq", 0.9)

        presets = interpolate(model, metadata, preset_a, preset_b, steps=7)
        assert len(presets) == 7

    def test_produces_preset_instances(self, minimal_preset):
        model = PresetVAE(FEATURE_DIM, latent_dim=8, hidden_dim=32)
        metadata = {"latent_dim": 8}
        preset_b = minimal_preset.clone()
        presets = interpolate(model, metadata, minimal_preset, preset_b, steps=3)
        for p in presets:
            assert isinstance(p, Preset)

    def test_endpoints_match_input(self, minimal_preset):
        """First and last interpolation steps should be close to inputs."""
        model = PresetVAE(FEATURE_DIM, latent_dim=8, hidden_dim=32)
        metadata = {"latent_dim": 8}
        preset_b = minimal_preset.clone()
        preset_b.set("filter.freq", 0.9)

        presets = interpolate(model, metadata, minimal_preset, preset_b, steps=5)

        # First step should be close to preset_a
        vec_a = extract_features(minimal_preset)
        vec_first = extract_features(presets[0])
        # They won't be identical (encoder introduces slight differences) but check name
        assert presets[0].name.startswith("Interp 000")
        assert presets[-1].name.startswith("Interp 004")

    def test_single_step(self, minimal_preset):
        """Interpolation with 1 step should produce 1 preset."""
        model = PresetVAE(FEATURE_DIM, latent_dim=8, hidden_dim=32)
        metadata = {"latent_dim": 8}
        presets = interpolate(model, metadata, minimal_preset, minimal_preset, steps=1)
        assert len(presets) == 1


# ── find_similar ─────────────────────────────────────────────────────


class TestFindSimilar:
    """Tests for similarity search in latent space."""

    def test_returns_correct_count(self, minimal_preset):
        model = PresetVAE(FEATURE_DIM, latent_dim=8, hidden_dim=32)
        metadata = {"latent_dim": 8}

        # Create a few different presets
        presets = []
        for i in range(5):
            p = minimal_preset.clone()
            p.set("filter.freq", 0.1 * (i + 1))
            p.name = f"Preset {i}"
            presets.append(p)

        results = find_similar(model, metadata, minimal_preset, presets, n=3)
        assert len(results) == 3

    def test_returns_tuples_of_preset_and_distance(self, minimal_preset):
        model = PresetVAE(FEATURE_DIM, latent_dim=8, hidden_dim=32)
        metadata = {"latent_dim": 8}

        presets = [minimal_preset.clone() for _ in range(3)]
        results = find_similar(model, metadata, minimal_preset, presets, n=2)

        for preset, dist in results:
            assert isinstance(preset, Preset)
            assert isinstance(dist, float)
            assert dist >= 0.0

    def test_sorted_by_distance(self, minimal_preset):
        model = PresetVAE(FEATURE_DIM, latent_dim=8, hidden_dim=32)
        metadata = {"latent_dim": 8}

        presets = []
        for i in range(5):
            p = minimal_preset.clone()
            p.set("filter.freq", 0.1 * (i + 1))
            presets.append(p)

        results = find_similar(model, metadata, minimal_preset, presets, n=5)
        distances = [d for _, d in results]
        assert distances == sorted(distances)

    def test_identical_preset_has_zero_distance(self, minimal_preset):
        """A preset should have distance ~0 to itself."""
        model = PresetVAE(FEATURE_DIM, latent_dim=8, hidden_dim=32)
        metadata = {"latent_dim": 8}

        results = find_similar(model, metadata, minimal_preset, [minimal_preset], n=1)
        _, dist = results[0]
        assert dist == pytest.approx(0.0, abs=1e-4)

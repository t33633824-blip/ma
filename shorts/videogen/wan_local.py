"""Локальная генерация видео моделями Wan (Alibaba, лицензия Apache 2.0) через diffusers.

Пресеты:
- wan22-5b   Wan2.2 TI2V-5B, 704x1280, 24 к/с. Лучшее качество среди тех, что влезают в 24 ГБ. ~2-5 мин на клип.
- wan21-1.3b Wan2.1 T2V-1.3B, 480x832, 16 к/с. Быстро, влезает в 8 ГБ. Качество попроще, хорош для черновиков.
- wan21-14b  Wan2.1 T2V-14B, 720x1280, 16 к/с. Очень медленно на 24 ГБ (выгрузка на CPU), но самая детальная картинка.

Первый запуск скачивает модель с Hugging Face: 5B около 20 ГБ, 1.3B около 6 ГБ, 14B около 60 ГБ.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from .base import clip_cache_key

log = logging.getLogger(__name__)

NEGATIVE_PROMPT = (
    "text, subtitles, captions, watermark, logo, ui, bright tones, overexposed, static, blurred details, "
    "worst quality, low quality, jpeg artifacts, ugly, incomplete, extra fingers, poorly drawn hands, "
    "poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, "
    "many people in the background, walking backwards"
)


@dataclass(frozen=True)
class Preset:
    repo: str
    width: int
    height: int
    fps: int
    max_frames: int
    default_steps: int
    guidance: float
    flow_shift: float | None  # для 2.1 через UniPC; для 2.2 оставляем планировщик по умолчанию


PRESETS = {
    "wan22-5b": Preset("Wan-AI/Wan2.2-TI2V-5B-Diffusers", 704, 1280, 24, 121, 40, 5.0, None),
    "wan21-1.3b": Preset("Wan-AI/Wan2.1-T2V-1.3B-Diffusers", 480, 832, 16, 81, 30, 5.0, 5.0),
    "wan21-14b": Preset("Wan-AI/Wan2.1-T2V-14B-Diffusers", 720, 1280, 16, 81, 30, 5.0, 5.0),
}


class WanLocal:
    def __init__(self, preset: str = "wan22-5b", steps: int | None = None, offload: bool = True, clips_dir: Path = Path("assets/clips"), models_dir: Path | None = None):
        if preset not in PRESETS:
            raise ValueError(f"Неизвестный пресет {preset}, доступны: {', '.join(PRESETS)}")
        self.preset_name = preset
        self.p = PRESETS[preset]
        self.steps = steps or self.p.default_steps
        self.offload = offload
        self.clips_dir = Path(clips_dir)
        self.models_dir = Path(models_dir) if models_dir else None
        self.fps = self.p.fps
        self._pipe = None

    # ---- загрузка модели

    def _load(self):
        if self._pipe is not None:
            return self._pipe
        try:
            import torch
            from diffusers import AutoencoderKLWan, WanPipeline
        except ImportError as e:  # noqa: F841
            raise RuntimeError("Не установлены зависимости генерации видео. Запусти: bash install.sh --video") from None
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA не найдена: генерация видео требует видеокарту NVIDIA с драйвером")
        free, total = torch.cuda.mem_get_info()
        log.info("GPU: %s, свободно %.1f из %.1f ГБ. Загружаю %s…", torch.cuda.get_device_name(0), free / 1e9, total / 1e9, self.p.repo)
        kw = {"cache_dir": str(self.models_dir)} if self.models_dir else {}
        t0 = time.time()
        vae = AutoencoderKLWan.from_pretrained(self.p.repo, subfolder="vae", torch_dtype=torch.float32, **kw)
        pipe = WanPipeline.from_pretrained(self.p.repo, vae=vae, torch_dtype=torch.bfloat16, **kw)
        if self.p.flow_shift is not None:
            from diffusers import UniPCMultistepScheduler

            pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config, flow_shift=self.p.flow_shift)
        if self.offload:
            pipe.enable_model_cpu_offload()  # веса подгружаются на GPU по очереди, экономит несколько ГБ
        else:
            pipe.to("cuda")
        for name in ("enable_tiling", "enable_slicing"):
            fn = getattr(pipe.vae, name, None)
            if callable(fn):
                try:
                    fn()
                except Exception:  # noqa: BLE001
                    pass
        log.info("Модель загружена за %.0f c", time.time() - t0)
        self._pipe = pipe
        return pipe

    # ---- генерация

    def frames_for(self, seconds: float) -> int:
        # Wan требует число кадров вида 4k+1
        n = int(round(seconds * self.p.fps))
        n = -(-(n - 1) // 4) * 4 + 1  # вверх до ближайшего 4k+1
        return max(17, min(self.p.max_frames, n))

    def generate(self, prompt: str, seconds: float, seed: int | None = None) -> Path:
        import torch
        from diffusers.utils import export_to_video

        num_frames = self.frames_for(seconds)
        key = clip_cache_key(self.preset_name, self.steps, num_frames, seed, prompt)
        self.clips_dir.mkdir(parents=True, exist_ok=True)
        out = self.clips_dir / f"{key}.mp4"
        if out.exists():
            log.info("Клип из кэша: %s", out.name)
            return out
        pipe = self._load()
        gen = torch.Generator(device="cuda").manual_seed(seed) if seed is not None else None
        log.info("Генерирую %d кадров %dx%d, %d шагов: %s", num_frames, self.p.width, self.p.height, self.steps, prompt[:90])
        t0 = time.time()
        result = pipe(
            prompt=prompt,
            negative_prompt=NEGATIVE_PROMPT,
            height=self.p.height,
            width=self.p.width,
            num_frames=num_frames,
            guidance_scale=self.p.guidance,
            num_inference_steps=self.steps,
            generator=gen,
        )
        export_to_video(result.frames[0], str(out), fps=self.p.fps)
        log.info("Клип готов за %.0f c: %s", time.time() - t0, out.name)
        return out

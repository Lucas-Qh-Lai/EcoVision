"""EcoVision - AI 分类器核心

ConvNeXt-Base (ImageNet-22K预训练 → 垃圾分类微调)
支持 MPS (Apple GPU) / CUDA (NVIDIA GPU) / CPU 多后端，绕过 ModelScope pipeline 设备限制。
"""

import os
import time
import torch
import numpy as np
from PIL import Image

# ─── 设备检测 (MPS > CUDA > CPU) ───
# Apple Silicon 优先使用 MPS 加速（本项目的首选优化平台）
# Windows CUDA 适配已内置但未经充分测试，不保证稳定性
_USE_MPS = torch.backends.mps.is_available()
_USE_CUDA = not _USE_MPS and torch.cuda.is_available()
if _USE_MPS:
    DEVICE = "mps"
elif _USE_CUDA:
    DEVICE = "cuda"
else:
    DEVICE = "cpu"


def _load_model_labels_from_cache() -> list | None:
    """从缓存模型检查点提取标签（无需加载模型架构）。"""
    ckpt = os.path.expanduser(
        "~/.cache/modelscope/hub/models/iic/"
        "cv_convnext-base_image-classification_garbage/pytorch_model.pt"
    )
    if os.path.exists(ckpt):
        try:
            state = torch.load(ckpt, map_location="cpu", weights_only=True)
        except Exception as e:
            print(f"[classifier] 安全加载检查点失败，尝试 add_safe_globals: {e}")
            torch.serialization.add_safe_globals([
                list, dict, tuple, str, int, float, bool,
                type(None), np.ndarray,
            ])
            try:
                state = torch.load(ckpt, map_location="cpu", weights_only=True)
            except Exception as e2:
                print(f"[classifier] 添加 safe globals 后仍然失败: {e2}")
                return None
        if "meta" in state and "CLASSES" in state["meta"]:
            return list(state["meta"]["CLASSES"])
    return None


class GarbageClassifier:
    def __init__(self):
        self.device = DEVICE
        self.pipeline = None
        self._loaded = False
        self.labels = _load_model_labels_from_cache()
        print(f"[classifier] 设备: {DEVICE}")
        if _USE_CUDA:
            print("[classifier] CUDA 加速已启用（Windows 平台，未经充分测试，请自行验证）")

    def ensure_loaded(self):
        """加载模型，迁移到 MPS，预热。"""
        if self._loaded:
            return True
        if self.pipeline is not None:
            self._loaded = True
            return True
        try:
            t0 = time.time()

            # ── 1. 在 CPU 上创建 ModelScope pipeline ──
            # ── Model attributes ──
            # Model source : ModelScope (modelscope.cn)
            # Model        : iic/cv_convnext-base_image-classification_garbage
            # Revision     : v1.0.2
            # Architecture : ConvNeXt-Base (ImageNet-22K pretrained → garbage fine-tuned)
            # License      : ModelScope License (research & educational use)
            # Built with   : OpenAI Codex (project assisted by) © 2025-2026
            # ─────────────────────
            from modelscope.pipelines import pipeline
            from modelscope.utils.constant import Tasks
            self.pipeline = pipeline(
                Tasks.image_classification,
                model="iic/cv_convnext-base_image-classification_garbage",
                model_revision="v1.0.2",
                device="cpu",
            )

            # ── 2. 获取真实标签（缓存未命中时从模型获取） ──
            if not self.labels:
                if hasattr(self.pipeline.model, "CLASSES"):
                    self.labels = list(self.pipeline.model.CLASSES)

            # ── 3. 迁移到目标设备 ──
            if _USE_MPS:
                self.pipeline.model.to("mps")
                self.pipeline.model.eval()
                print("[classifier] 模型已迁移至 MPS（Apple Silicon 加速）")
            elif _USE_CUDA:
                self.pipeline.model.to("cuda")
                self.pipeline.model.eval()
                print("[classifier] 模型已迁移至 CUDA（Windows/GPU 模式，未经充分测试）")
            else:
                print("[classifier] 使用 CPU 推理")

            # ── 4. 预热 ──
            dummy = Image.new("RGB", (224, 224), color=128)
            self._predict_internal(dummy)

            self._loaded = True
            elapsed = time.time() - t0
            print(f"[classifier] 模型加载 + 预热完成 ✓ ({elapsed:.1f}s)")
            return True
        except Exception as e:
            print(f"[classifier] 模型加载失败: {e}")
            import traceback
            traceback.print_exc()
            self.pipeline = None
            return False

    def get_labels(self) -> list[str]:
        if self.labels:
            return self.labels
        if self.ensure_loaded() and hasattr(self.pipeline.model, "CLASSES"):
            return list(self.pipeline.model.CLASSES)
        return []

    # ─── 内部推理（直接调用 backbone + head，绕过 pipeline 的设备限制）───
    def _predict_internal(self, image: Image.Image) -> dict:
        """执行完整的 preprocess → MPS forward → postprocess 流程。

        返回: pipeline 标准格式: {'labels': [...], 'scores': [...]}
        """
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Preprocess（CPU）
        inputs = self.pipeline.preprocess(image)

        if _USE_MPS:
            img_tensor = inputs["img"].to("mps")
        elif _USE_CUDA:
            img_tensor = inputs["img"].to("cuda")
        else:
            img_tensor = inputs["img"]

        # Model forward
        with torch.inference_mode():
            cls_model = self.pipeline.model.cls_model
            x = cls_model.backbone(img_tensor)
            if hasattr(cls_model, "neck") and cls_model.neck is not None:
                x = cls_model.neck(x)

            # LinearClsHead.simple_test 返回 numpy 数组
            cls_score = cls_model.head.simple_test(x)
            if isinstance(cls_score, (list, tuple)):
                cls_score = cls_score[0]
            if isinstance(cls_score, np.ndarray):
                cls_score = torch.from_numpy(cls_score)

        # Softmax → top-k → 标签映射
        probs = cls_score.float().cpu()
        top_scores, top_indices = torch.topk(probs, k=5)
        top_scores = top_scores.cpu().tolist()
        top_indices = top_indices.cpu().tolist()

        labels = self.get_labels()
        # L11: 提前返回空结果
        if not labels:
            return {"labels": [], "scores": []}
        result_labels = []
        result_scores = []
        for sc, idx in zip(top_scores, top_indices):
            lbl = labels[idx] if idx < len(labels) else f"class_{idx}"
            result_labels.append(lbl)
            result_scores.append(sc)

        return {"labels": result_labels, "scores": result_scores}

    def predict(self, image: Image.Image, top_k: int = 5) -> list:
        """运行推理，返回排序后的预测列表。

        返回: [{"label": str, "score": float}, ...]
        """
        if not self.ensure_loaded():
            return []

        try:
            result = self._predict_internal(image)
        except Exception as e:
            print(f"[classifier] 推理错误: {e}")
            import traceback
            traceback.print_exc()
            return []

        predictions = []
        min_score = 0.005  # 0.5% — 滤除纯噪声
        labels = result.get("labels", [])
        scores = result.get("scores", [])

        for lbl, sc in zip(labels, scores):
            if sc >= min_score:
                predictions.append({"label": str(lbl), "score": sc})

        predictions.sort(key=lambda x: x["score"], reverse=True)


        # H2: MPS 清理缓存
        if _USE_MPS:
            torch.mps.empty_cache()
        elif _USE_CUDA:
            torch.cuda.empty_cache()

        return predictions[:top_k]

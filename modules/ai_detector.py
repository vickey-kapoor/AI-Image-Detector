"""AI Image Detector using umm-maybe/AI-image-detector model (94.2% accuracy)"""

import time
from typing import Any, Dict

import torch
from PIL import Image
from transformers import pipeline

MAX_IMAGE_DIMENSION = 1024


class AIImageDetector:
    """Detect AI-generated images using ViT-based classifier"""

    def __init__(self, model_name: str = "umm-maybe/AI-image-detector"):
        """
        Initialize the AI image detector.

        Args:
            model_name: HuggingFace model identifier
        """
        print(f"Loading AI Image Detector model: {model_name}")
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {self.device}")

        # Load the image classification pipeline
        self.classifier = pipeline(
            "image-classification",
            model=model_name,
            device=0 if self.device == "cuda" else -1
        )

        print("AI Image Detector model loaded successfully!")

    @staticmethod
    def _resize_if_needed(image: Image.Image) -> Image.Image:
        """Resize oversized images before classification (ViT expects 224x224)."""
        w, h = image.size
        if w > MAX_IMAGE_DIMENSION or h > MAX_IMAGE_DIMENSION:
            ratio = min(MAX_IMAGE_DIMENSION / w, MAX_IMAGE_DIMENSION / h)
            new_size = (int(w * ratio), int(h * ratio))
            image = image.resize(new_size, Image.LANCZOS)
        return image

    def analyze_image(self, image: Image.Image) -> Dict[str, Any]:
        """
        Analyze an image to determine if it's AI-generated.

        Args:
            image: PIL Image object

        Returns:
            dict with detection results
        """
        start_time = time.perf_counter()

        # Ensure RGB
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Resize oversized images
        image = self._resize_if_needed(image)

        # Run classification
        results = self.classifier(image)

        # Parse results - model returns labels 'artificial' and 'human'
        artificial_score = 0.0
        human_score = 0.0

        for result in results:
            label = result['label'].lower()
            score = result['score']
            if label == 'artificial':
                artificial_score = score
            elif label == 'human':
                human_score = score

        # Determine verdict
        if artificial_score > 0.6:
            verdict = 'Likely AI'
            is_ai = True
            confidence = artificial_score
        elif human_score > 0.6:
            verdict = 'Likely Real'
            is_ai = False
            confidence = human_score
        else:
            verdict = 'Uncertain'
            is_ai = False
            confidence = max(artificial_score, human_score)

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        return {
            'is_ai': is_ai,
            'confidence': confidence,
            'verdict': verdict,
            'full_analysis': f"AI: {artificial_score*100:.1f}%, Human: {human_score*100:.1f}%",
            'fake_probability': artificial_score,
            'real_probability': human_score,
            'processing_time_ms': processing_time_ms
        }

    def get_model_info(self) -> Dict[str, str]:
        """Get model information."""
        return {
            'name': self.model_name,
            'device': self.device,
            'accuracy': '94.2%'
        }

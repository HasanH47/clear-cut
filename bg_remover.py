import asyncio
import io
import logging
from typing import Union
import numpy as np
from PIL import Image
import cv2
from rembg import new_session, remove
import onnxruntime as ort

logger = logging.getLogger(__name__)

class BackgroundRemover:
    def __init__(self):
        self.session = None
        self.model_name = "u2net"  # High quality model
        
    async def initialize(self):
        """Initialize the background removal model"""
        try:
            logger.info(f"Loading {self.model_name} model...")
            
            # Configure ONNX Runtime for CPU optimization
            ort.set_default_logger_severity(3)  # Suppress warnings
            
            # Initialize rembg session with optimized settings
            self.session = new_session(
                model_name=self.model_name,
                providers=['CPUExecutionProvider'],
                provider_options=[{
                    'intra_op_num_threads': 2,  # Optimize for 2 core VPS
                    'inter_op_num_threads': 1,
                    'enable_mem_pattern': True,
                    'enable_mem_reuse': True,
                }]
            )
            
            logger.info("Background remover initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize background remover: {e}")
            raise

    async def remove_background(self, image_data: Union[bytes, Image.Image]) -> Image.Image:
        """Remove background from image"""
        try:
            # Convert input to PIL Image if needed
            if isinstance(image_data, bytes):
                original_image = Image.open(io.BytesIO(image_data))
            else:
                original_image = image_data
            
            # Ensure image is in RGB mode
            if original_image.mode != 'RGB':
                original_image = original_image.convert('RGB')
            
            # Get original size
            original_size = original_image.size
            
            # Resize for processing if too large (memory optimization)
            max_size = 2048
            if max(original_size) > max_size:
                ratio = max_size / max(original_size)
                new_size = tuple(int(dim * ratio) for dim in original_size)
                processing_image = original_image.resize(new_size, Image.Resampling.LANCZOS)
            else:
                processing_image = original_image
            
            # Convert to bytes for rembg
            img_byte_arr = io.BytesIO()
            processing_image.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()
            
            # Run background removal in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result_bytes = await loop.run_in_executor(
                None, 
                self._remove_bg_sync, 
                img_bytes
            )
            
            # Convert back to PIL Image
            result_image = Image.open(io.BytesIO(result_bytes))
            
            # Resize back to original size if it was resized
            if max(original_size) > max_size:
                result_image = result_image.resize(original_size, Image.Resampling.LANCZOS)
            
            # Post-process to improve quality
            result_image = self._post_process_image(result_image)
            
            return result_image
            
        except Exception as e:
            logger.error(f"Background removal failed: {e}")
            raise

    def _remove_bg_sync(self, image_bytes: bytes) -> bytes:
        """Synchronous background removal"""
        return remove(image_bytes, session=self.session)

    def _post_process_image(self, image: Image.Image) -> Image.Image:
        """Post-process the image to improve quality"""
        try:
            # Convert to numpy array
            img_array = np.array(image)
            
            # Apply alpha matting refinement
            if img_array.shape[2] == 4:  # RGBA
                # Get alpha channel
                alpha = img_array[:, :, 3]
                
                # Apply morphological operations to clean up edges
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                alpha_cleaned = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, kernel)
                alpha_cleaned = cv2.morphologyEx(alpha_cleaned, cv2.MORPH_OPEN, kernel)
                
                # Apply Gaussian blur to soften harsh edges
                alpha_smooth = cv2.GaussianBlur(alpha_cleaned, (3, 3), 0.5)
                
                # Update alpha channel
                img_array[:, :, 3] = alpha_smooth
                
                # Convert back to PIL Image
                result_image = Image.fromarray(img_array, 'RGBA')
                
                return result_image
            
            return image
            
        except Exception as e:
            logger.warning(f"Post-processing failed, returning original: {e}")
            return image

    def _enhance_edges(self, image: Image.Image) -> Image.Image:
        """Enhance edges using machine learning techniques"""
        try:
            # Convert to numpy array
            img_array = np.array(image)
            
            if img_array.shape[2] == 4:  # RGBA
                # Get alpha channel
                alpha = img_array[:, :, 3].astype(np.float32) / 255.0
                
                # Create distance transform for better edge detection
                alpha_binary = (alpha > 0.5).astype(np.uint8) * 255
                dist_transform = cv2.distanceTransform(alpha_binary, cv2.DIST_L2, 5)
                
                # Normalize and apply sigmoid for smooth falloff
                dist_normalized = dist_transform / np.max(dist_transform) if np.max(dist_transform) > 0 else dist_transform
                alpha_enhanced = 1 / (1 + np.exp(-10 * (dist_normalized - 0.1)))
                
                # Combine with original alpha
                alpha_final = np.maximum(alpha, alpha_enhanced * 0.3)
                alpha_final = np.clip(alpha_final * 255, 0, 255).astype(np.uint8)
                
                # Update alpha channel
                img_array[:, :, 3] = alpha_final
                
                return Image.fromarray(img_array, 'RGBA')
            
            return image
            
        except Exception as e:
            logger.warning(f"Edge enhancement failed: {e}")
            return image

    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.session:
                # rembg sessions don't need explicit cleanup
                self.session = None
            logger.info("Background remover cleanup completed")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    def get_model_info(self) -> dict:
        """Get information about the loaded model"""
        return {
            "model_name": self.model_name,
            "status": "loaded" if self.session else "not_loaded",
            "description": "U²-Net model for high-quality background removal"
        }

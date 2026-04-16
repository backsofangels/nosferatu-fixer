"""EPUB utilities for common operations."""

from pathlib import Path
from typing import Optional
from zipfile import ZipFile


class EPUBRepackingError(Exception):
    """Raised when EPUB repacking fails."""
    pass


class EPUBRepackager:
    """Handle EPUB repacking with standard compression settings."""
    
    @staticmethod
    def repack_from_temp_dir(temp_dir: Path, output_path: str) -> bool:
        """
        Repack EPUB from temporary directory.
        
        Preserves mimetype uncompressed (EPUB requirement).
        Compresses all other files.
        
        Args:
            temp_dir: Unpacked EPUB directory
            output_path: Output EPUB path
            
        Returns:
            True if successful
            
        Raises:
            EPUBRepackingError: If repacking fails
        """
        try:
            with ZipFile(output_path, "w") as out_zip:
                # Write mimetype first (uncompressed)
                mimetype_path = temp_dir / "mimetype"
                if mimetype_path.exists():
                    out_zip.write(mimetype_path, "mimetype", compress_type=0)
                
                # Write all other files (compressed)
                for file_path in temp_dir.rglob("*"):
                    if file_path.is_file() and file_path.name != "mimetype":
                        arcname = str(file_path.relative_to(temp_dir))
                        out_zip.write(file_path, arcname)
            
            return True
        except Exception as e:
            raise EPUBRepackingError(f"Failed to repack EPUB: {str(e)}")

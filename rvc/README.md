# RVC Models Directory

This directory contains RVC (Retrieval-based Voice Conversion) models for Turkish singing voice generation.

## Structure
- `models/` - Contains .pth model files
- `indices/` - Contains .index feature files

## Default Model
The application will automatically download a default Turkish female voice model if none exists.

## Adding Custom Models
1. Place your .pth model files in the `models/` directory
2. Place corresponding .index files in the `indices/` directory
3. Ensure file names match (e.g., `singer.pth` and `singer.index`)

## Model Sources
- Hugging Face: https://huggingface.co/models?search=rvc
- RVC Community: Various Discord servers and GitHub repositories
- Train your own: Use RVC-WebUI to train custom models

## Supported Formats
- Models: .pth files (PyTorch checkpoints)
- Indices: .index files (FAISS indices for retrieval)

## Note
The default model is a general-purpose Turkish voice model.
For best results with Turkish songs, consider using models trained specifically on Turkish singers.

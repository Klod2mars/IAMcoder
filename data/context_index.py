"""
Data Layer: Context Index
Indexation du code en embeddings avec ChromaDB
"""
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

from core.file_manager import file_manager
from core.settings import settings


class ContextIndexError(Exception):
    """Exception pour les erreurs d'index"""
    pass


class ContextIndex:
    """
    Indexation vectorielle du code pour la recherche sémantique.
    Utilise ChromaDB pour stocker les embeddings.
    """
    
    def __init__(self, persist_directory: Optional[str] = None):
        if not CHROMADB_AVAILABLE:
            raise ContextIndexError(
                "ChromaDB is not installed. Install it with: pip install chromadb"
            )
        
        self.persist_directory = persist_directory or str(settings.data_dir / "chroma_db")
        self.client = None
        self.collection = None
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialise le client ChromaDB"""
        try:
            self.client = chromadb.Client(ChromaSettings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=self.persist_directory,
                anonymized_telemetry=False
            ))
            
            # Crée ou récupère la collection
            self.collection = self.client.get_or_create_collection(
                name="code_index",
                metadata={"description": "Codebase semantic index"}
            )
        except Exception as e:
            raise ContextIndexError(f"Failed to initialize ChromaDB client: {str(e)}")
    
    def index_file(self, file_path: str, file_content: Optional[str] = None) -> None:
        """
        Indexe un fichier dans l'index vectoriel.
        
        Args:
            file_path: Le chemin du fichier à indexer
            file_content: Le contenu du fichier (si None, sera lu)
            
        Raises:
            ContextIndexError: Si l'indexation échoue
        """
        if file_content is None:
            try:
                file_content = file_manager.read_file(file_path)
            except Exception as e:
                raise ContextIndexError(f"Failed to read file {file_path}: {str(e)}")
        
        # Découpage en chunks pour les gros fichiers
        chunks = self._split_into_chunks(file_path, file_content)
        
        try:
            # Ajout des chunks à l'index
            documents = []
            metadatas = []
            ids = []
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{file_path}:{i}"
                documents.append(chunk)
                metadatas.append({
                    "file_path": file_path,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                })
                ids.append(chunk_id)
            
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
        except Exception as e:
            raise ContextIndexError(f"Failed to index file {file_path}: {str(e)}")
    
    def _split_into_chunks(self, file_path: str, content: str, chunk_size: int = 500) -> List[str]:
        """
        Découpe le contenu en chunks de taille raisonnable.
        
        Args:
            file_path: Le chemin du fichier
            content: Le contenu à découper
            chunk_size: La taille des chunks (en lignes)
            
        Returns:
            Liste des chunks
        """
        lines = content.splitlines()
        chunks = []
        
        for i in range(0, len(lines), chunk_size):
            chunk = "\n".join(lines[i:i + chunk_size])
            chunks.append(chunk)
        
        return chunks
    
    def query(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Recherche dans l'index vectoriel.
        
        Args:
            query_text: La requête de recherche
            n_results: Nombre de résultats à retourner
            
        Returns:
            Liste des résultats avec métadonnées
        """
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            
            # Formatage des résultats
            formatted_results = []
            
            if results['documents'] and results['documents'][0]:
                for i in range(len(results['documents'][0])):
                    formatted_results.append({
                        "document": results['documents'][0][i],
                        "distance": results['distances'][0][i] if results.get('distances') else None,
                        "metadata": results['metadatas'][0][i] if results.get('metadatas') else {}
                    })
            
            return formatted_results
            
        except Exception as e:
            raise ContextIndexError(f"Failed to query index: {str(e)}")
    
    def clear_index(self) -> None:
        """Vide l'index complet"""
        try:
            self.collection.delete()
            self.collection = self.client.create_collection(
                name="code_index",
                metadata={"description": "Codebase semantic index"}
            )
        except Exception as e:
            raise ContextIndexError(f"Failed to clear index: {str(e)}")


# Instance globale de l'index (initialisée seulement si utilisé)
context_index = None

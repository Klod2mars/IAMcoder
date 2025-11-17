"""
Presentation Layer: UI Diff View
Affichage des diffs avec Rich
"""
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from domain.entities import DiffResult


def safe_print(text: str) -> str:
    """Supprime les emojis pour compatibilité console Windows"""
    emoji_map = {
        "📝": "[DIFF]",
        "📊": "[SUMMARY]",
    }
    for emoji, replacement in emoji_map.items():
        text = text.replace(emoji, replacement)
    return text


class UIDiffView:
    """
    Gestionnaire d'affichage des diffs avec Rich.
    """
    
    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None
    
    def display_diff(self, diff_result: DiffResult) -> None:
        """
        Affiche un diff de manière élégante.
        
        Args:
            diff_result: Le résultat du diff à afficher
        """
        if not RICH_AVAILABLE:
            print(diff_result.to_unified_diff())
            return
        
        # Création d'un panel avec le résumé
        summary = diff_result.get_summary()
        panel_content = f"[cyan]{summary}[/cyan]\n\n"
        
        # Tableau des changements
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Ligne", style="dim", width=6)
        table.add_column("Type", width=10)
        table.add_column("Contenu", style="white")
        
        for diff_line in diff_result.diff_lines[:50]:  # Limite l'affichage
            line_type = diff_line.diff_type.value
            if diff_line.diff_type.value == "added":
                style = "green"
            elif diff_line.diff_type.value == "removed":
                style = "red"
            else:
                style = "yellow"
            
            content = diff_line.new_content if diff_line.diff_type.value != "removed" else diff_line.old_content
            
            table.add_row(
                str(diff_line.line_number),
                f"[{style}]{line_type}[/{style}]",
                content[:100]  # Limite la largeur
            )
        
        panel_content += str(table)
        
        if len(diff_result.diff_lines) > 50:
            panel_content += f"\n... et {len(diff_result.diff_lines) - 50} autres lignes"
        
        # Affichage du panel
        self.console.print(Panel(
            panel_content,
            title=safe_print(f"[bold]📝 Diff: {diff_result.file_path}[/bold]"),
            border_style="cyan"
        ))
    
    def display_diff_summary(self, diff_results: list) -> None:
        """
        Affiche un résumé de plusieurs diffs.
        
        Args:
            diff_results: Liste de DiffResult
        """
        if not diff_results:
            if self.console:
                self.console.print("[green]✓ No changes detected[/green]")
            else:
                print("No changes detected")
            return
        
        if not RICH_AVAILABLE:
            print("\nSummary of changes:")
            for result in diff_results:
                print(f"  {result.get_summary()}")
            return
        
        # Tableau de résumé
        table = Table(show_header=True, header_style="bold")
        table.add_column("Fichier", style="cyan")
        table.add_column("Ajouté", style="green")
        table.add_column("Supprimé", style="red")
        table.add_column("Modifié", style="yellow")
        
        total_added = 0
        total_removed = 0
        total_modified = 0
        
        for result in diff_results:
            table.add_row(
                result.file_path,
                str(result.added_lines),
                str(result.removed_lines),
                str(result.modified_lines)
            )
            total_added += result.added_lines
            total_removed += result.removed_lines
            total_modified += result.modified_lines
        
        # Affichage
        summary_text = f"[bold]Total:[/bold] +{total_added} -{total_removed} ~{total_modified}"
        self.console.print(Panel(
            table,
            title=safe_print("[bold]📊 Summary of Changes[/bold]"),
            border_style="green"
        ))
        self.console.print(f"[green]{summary_text}[/green]\n")


# Instance globale de la vue diff
ui_diff_view = UIDiffView()

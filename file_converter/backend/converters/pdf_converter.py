# converts files to pdf files
from pathlib import Path
from typing import Dict
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT, TA_CENTER

class PdfConversionError(Exception):
    """Custom exception for PDF conversion errors"""
    pass

def convert_to_pdf(article_data: Dict[str, str], output_path: Path) -> None:
    """
    Convert article data to a PDF file.
    
    Args:
        article_data: Dictionary with 'title' and 'text' keys
        output_path: Path object for the output file
    
    Raises:
        PdfConversionError: If conversion fails
    """
    try:
        title = article_data.get('title', 'Untitled')
        text = article_data.get('text', '')
        
        if not text:
            raise PdfConversionError("No text content to convert")
        
        # Create PDF document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=inch,
            leftMargin=inch,
            topMargin=inch,
            bottomMargin=inch
        )
        
        # Container for PDF elements
        story = []
        
        # Get default styles
        styles = getSampleStyleSheet()
        
        # Create custom title style
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor='#2c3e50',
            spaceAfter=20,
            alignment=TA_CENTER
        )
        
        # Create custom body style
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['BodyText'],
            fontSize=11,
            leading=16,
            alignment=TA_LEFT,
            spaceAfter=12
        )
        
        # Add title
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 0.3 * inch))
        
        # Split text into paragraphs and add to story
        paragraphs = text.split('\n\n')
        for para in paragraphs:
            if para.strip():
                # Clean the text for reportlab (escape special chars)
                clean_para = para.strip().replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(clean_para, body_style))
        
        # Build PDF
        doc.build(story)
        
    except PdfConversionError:
        raise
    
    except Exception as e:
        raise PdfConversionError(f"Failed to create PDF file: {str(e)}")
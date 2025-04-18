import PyPDF2
import re
import textwrap

def extract_raw_text(path_to_pdf):
    # Specify the PDF file path
    pdf_file = path_to_pdf

    # Open the PDF file
    with open(pdf_file, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        raw_text = ""

        # Iterate through all pages and extract text
        for page in reader.pages:
            raw_text += page.extract_text()
    return raw_text
    
def cut_intro(raw_text):
    raw_text = "Introduction".join(raw_text.split("Introduction")[1:])
    raw_text = "References".join(raw_text.split("References")[:-1])
    return raw_text

def prettify_text(raw_text, width=80):
    """
    Prettifies raw extracted text by removing extraneous whitespace,
    bracket references, and reflowing paragraphs to a given width.
    
    Parameters:
    -----------
    raw_text : str
        The raw text you want to prettify.
    width : int
        The line width for wrapping (default=80).
    
    Returns:
    --------
    str
        A cleaned-up and nicely formatted version of the text.
    """
    # 1. Normalize line endings (just in case they're inconsistent)
    text = raw_text.replace('\r\n', '\n')
    text = text.replace('\r', '\n')

    # 2. Remove bracket references like [21], [ 3,14,16,34], etc.
    #    Pattern: A literal '[' followed by anything not ']', then a literal ']'
    #    We allow nested spaces, digits, commas, etc. inside the brackets.
    text = re.sub(r'\[[^\]]*\]', '', text)

    # 3. Remove extra spaces (2+ spaces -> 1 space)
    text = re.sub(r' {2,}', ' ', text)

    # 4. Split into paragraphs by blank lines
    paragraphs = re.split(r'\n\s*\n+', text)

    cleaned_paragraphs = []
    for paragraph in paragraphs:
        # Strip leading/trailing whitespace
        paragraph = paragraph.strip()

        if not paragraph:
            # Skip empty paragraphs
            continue

        # 5. Merge any leftover newlines within the paragraph
        #    We'll treat newlines as spaces unless they end a sentence
        #    (simple heuristic: if line ends in . ? ! :)
        #    This step attempts to remove mid-sentence line breaks.
        lines = paragraph.split('\n')
        merged = []
        for line in lines:
            line = line.strip()
            if not merged:
                merged.append(line)
            else:
                # If the previous line ends with punctuation that suggests sentence end, start a new sentence.
                if re.search(r'[.!?;:]\s*$', merged[-1]):
                    merged[-1] = merged[-1].rstrip()
                    merged.append(line)
                else:
                    # Otherwise, continue on the same line with a space
                    merged[-1] = merged[-1].rstrip() + ' ' + line

        # Now merge the re-joined lines into a single string
        paragraph_merged = ' '.join(merged)

        # 6. Optionally wrap text to a given width using textwrap
        wrapped = textwrap.fill(paragraph_merged, width=width)

        cleaned_paragraphs.append(wrapped)

    # 7. Rejoin paragraphs with a blank line between them
    prettified = '\n\n'.join(cleaned_paragraphs)

    return prettified

def remove_gid_patterns_preserve_paragraphs(text):
    paragraphs = text.split('\n\n')  # naive paragraph split
    cleaned_paragraphs = []
    for para in paragraphs:
        # Flatten only within a paragraph (replace single \n with spaces, not double \n\n)
        single_line = para.replace('\n', ' ')
        single_line = re.sub(r'\s+', ' ', single_line)

        single_line = re.sub(r'/gid(?:\s*\d)+', '', single_line)
        single_line = re.sub(r'\s+', ' ', single_line).strip()
        cleaned_paragraphs.append(single_line)

    return '\n\n'.join(cleaned_paragraphs)

def get_clean_text(path_to_pdf):
    raw_text = extract_raw_text(path_to_pdf)
    raw_text = cut_intro(raw_text)
    prettified_output = prettify_text(raw_text, width=80)
    text_of_paper = remove_gid_patterns_preserve_paragraphs(prettified_output)  
    return text_of_paper


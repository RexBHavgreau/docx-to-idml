import JSZip from 'jszip';

export interface DocxParagraph {
  text: string;
  style: string;
  isBold: boolean;
  isItalic: boolean;
  isUnderline: boolean;
  fontSize: number | null;
  fontName: string | null;
  alignment: 'left' | 'center' | 'right' | 'justify';
  runs: DocxRun[];
}

export interface DocxRun {
  text: string;
  isBold: boolean;
  isItalic: boolean;
  isUnderline: boolean;
  fontSize: number | null;
  fontName: string | null;
}

export interface DocxStyle {
  id: string;
  name: string;
  type: 'paragraph' | 'character';
  basedOn?: string;
  fontSize?: number;
  fontName?: string;
  isBold?: boolean;
  isItalic?: boolean;
}

export interface DocxContent {
  paragraphs: DocxParagraph[];
  styles: DocxStyle[];
  fonts: Set<string>;
  title: string;
}

function getXmlText(element: Element, tagName: string): string {
  const el = element.getElementsByTagNameNS('*', tagName)[0];
  return el?.textContent || '';
}

function getXmlAttr(element: Element, attr: string): string {
  return element.getAttribute(attr) || '';
}

function parseRunProperties(rPr: Element | null): Partial<DocxRun> {
  if (!rPr) return {};

  const result: Partial<DocxRun> = {};

  const bold = rPr.getElementsByTagNameNS('*', 'b')[0];
  if (bold) {
    const val = bold.getAttribute('w:val');
    result.isBold = val !== '0' && val !== 'false';
  }

  const italic = rPr.getElementsByTagNameNS('*', 'i')[0];
  if (italic) {
    const val = italic.getAttribute('w:val');
    result.isItalic = val !== '0' && val !== 'false';
  }

  const underline = rPr.getElementsByTagNameNS('*', 'u')[0];
  if (underline) {
    const val = underline.getAttribute('w:val');
    result.isUnderline = val !== 'none' && val !== '' && val !== '0';
  }

  const sz = rPr.getElementsByTagNameNS('*', 'sz')[0];
  if (sz) {
    const val = sz.getAttribute('w:val');
    if (val) result.fontSize = parseInt(val) / 2; // half-points to points
  }

  const rFonts = rPr.getElementsByTagNameNS('*', 'rFonts')[0];
  if (rFonts) {
    result.fontName = rFonts.getAttribute('w:ascii') || rFonts.getAttribute('w:cs') || null;
  }

  return result;
}

function parseParagraphProperties(pPr: Element | null): {
  style: string;
  alignment: 'left' | 'center' | 'right' | 'justify';
} {
  if (!pPr) return { style: 'Normal', alignment: 'left' };

  let style = 'Normal';
  const pStyle = pPr.getElementsByTagNameNS('*', 'pStyle')[0];
  if (pStyle) {
    style = pStyle.getAttribute('w:val') || 'Normal';
  }

  let alignment: 'left' | 'center' | 'right' | 'justify' = 'left';
  const jc = pPr.getElementsByTagNameNS('*', 'jc')[0];
  if (jc) {
    const val = jc.getAttribute('w:val');
    if (val === 'center') alignment = 'center';
    else if (val === 'right') alignment = 'right';
    else if (val === 'both' || val === 'distribute') alignment = 'justify';
  }

  return { style, alignment };
}

export async function parseDocx(file: File): Promise<DocxContent> {
  const arrayBuffer = await file.arrayBuffer();
  const zip = await JSZip.loadAsync(arrayBuffer);

  // Parse document.xml
  const documentXml = await zip.file('word/document.xml')?.async('string');
  if (!documentXml) throw new Error('Invalid DOCX file: missing document.xml');

  const parser = new DOMParser();
  const doc = parser.parseFromString(documentXml, 'application/xml');

  // Parse styles.xml
  const stylesXml = await zip.file('word/styles.xml')?.async('string');
  const styles: DocxStyle[] = [];
  const fonts = new Set<string>();
  fonts.add('Arial');
  fonts.add('Times New Roman');

  if (stylesXml) {
    const stylesDoc = parser.parseFromString(stylesXml, 'application/xml');
    const styleElements = stylesDoc.getElementsByTagNameNS('*', 'style');

    for (let i = 0; i < styleElements.length; i++) {
      const styleEl = styleElements[i];
      const type = styleEl.getAttribute('w:type') || 'paragraph';
      const id = styleEl.getAttribute('w:styleId') || '';
      const name = getXmlText(styleEl, 'name');

      const style: DocxStyle = {
        id,
        name: name || id,
        type: type as 'paragraph' | 'character',
      };

      const basedOn = styleEl.getElementsByTagNameNS('*', 'basedOn')[0];
      if (basedOn) {
        style.basedOn = basedOn.getAttribute('w:val') || undefined;
      }

      const rPr = styleEl.getElementsByTagNameNS('*', 'rPr')[0];
      if (rPr) {
        const props = parseRunProperties(rPr);
        if (props.fontSize) style.fontSize = props.fontSize;
        if (props.fontName) {
          style.fontName = props.fontName;
          fonts.add(props.fontName);
        }
        if (props.isBold) style.isBold = true;
        if (props.isItalic) style.isItalic = true;
      }

      styles.push(style);
    }
  }

  // Parse paragraphs
  const body = doc.getElementsByTagNameNS('*', 'body')[0];
  const paragraphElements = body?.getElementsByTagNameNS('*', 'p') || [];
  const paragraphs: DocxParagraph[] = [];
  let title = '';

  for (let i = 0; i < paragraphElements.length; i++) {
    const pEl = paragraphElements[i];
    const pPr = pEl.getElementsByTagNameNS('*', 'pPr')[0] || null;
    const paraProps = parseParagraphProperties(pPr);

    const runs: DocxRun[] = [];
    let fullText = '';

    const runElements = pEl.getElementsByTagNameNS('*', 'r');
    for (let j = 0; j < runElements.length; j++) {
      const rEl = runElements[j];
      const rPr = rEl.getElementsByTagNameNS('*', 'rPr')[0] || null;
      const runProps = parseRunProperties(rPr);

      // Get text content
      const textElements = rEl.getElementsByTagNameNS('*', 't');
      let runText = '';
      for (let k = 0; k < textElements.length; k++) {
        runText += textElements[k].textContent || '';
      }

      // Also check for breaks
      const brElements = rEl.getElementsByTagNameNS('*', 'br');
      if (brElements.length > 0 && runText === '') {
        runText = '\n';
      }

      if (runText) {
        const run: DocxRun = {
          text: runText,
          isBold: runProps.isBold || false,
          isItalic: runProps.isItalic || false,
          isUnderline: runProps.isUnderline || false,
          fontSize: runProps.fontSize || null,
          fontName: runProps.fontName || null,
        };
        runs.push(run);
        fullText += runText;

        if (run.fontName) fonts.add(run.fontName);
      }
    }

    // Determine paragraph-level formatting from first run
    const firstRunProps: DocxRun = runs.length > 0 ? runs[0] : {
      text: '', isBold: false, isItalic: false, isUnderline: false, fontSize: null, fontName: null
    };

    const paragraph: DocxParagraph = {
      text: fullText,
      style: paraProps.style,
      isBold: firstRunProps.isBold || false,
      isItalic: firstRunProps.isItalic || false,
      isUnderline: firstRunProps.isUnderline || false,
      fontSize: firstRunProps.fontSize || null,
      fontName: firstRunProps.fontName || null,
      alignment: paraProps.alignment,
      runs,
    };

    paragraphs.push(paragraph);

    // Capture title
    if (!title && fullText.trim() && (paraProps.style.toLowerCase().includes('title') || paraProps.style.toLowerCase().includes('heading1'))) {
      title = fullText.trim();
    }
  }

  // If no title found, use first non-empty paragraph
  if (!title) {
    const firstNonEmpty = paragraphs.find(p => p.text.trim());
    if (firstNonEmpty) title = firstNonEmpty.text.trim().substring(0, 50);
  }

  return {
    paragraphs,
    styles,
    fonts,
    title: title || 'Untitled Document',
  };
}

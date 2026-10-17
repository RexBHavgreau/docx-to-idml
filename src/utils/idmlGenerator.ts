import JSZip from 'jszip';
import type { DocxContent, DocxParagraph, DocxStyle } from './docxParser';

let idCounter = 100;
function nextId(): string {
  return `u${(idCounter++).toString(16)}`;
}

function escapeXml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function mapDocxStyleToIdml(styleId: string): string {
  const lower = styleId.toLowerCase();
  if (lower.includes('heading1') || lower === '1') return 'ParagraphStyle/Heading1';
  if (lower.includes('heading2') || lower === '2') return 'ParagraphStyle/Heading2';
  if (lower.includes('heading3') || lower === '3') return 'ParagraphStyle/Heading3';
  if (lower.includes('heading4') || lower === '4') return 'ParagraphStyle/Heading4';
  if (lower.includes('title')) return 'ParagraphStyle/Title';
  if (lower.includes('subtitle')) return 'ParagraphStyle/Subtitle';
  if (lower.includes('quote') || lower.includes('blockquote')) return 'ParagraphStyle/Quote';
  if (lower.includes('list') || lower.includes('bullet')) return 'ParagraphStyle/ListBullet';
  if (lower.includes('code') || lower.includes('preformatted')) return 'ParagraphStyle/Code';
  if (lower === 'normal' || lower === 'bodytext' || lower === 'body') return 'ParagraphStyle/$ID/NormalParagraphStyle';
  return 'ParagraphStyle/$ID/NormalParagraphStyle';
}

function getAlignmentValue(alignment: string): string {
  switch (alignment) {
    case 'center': return 'CenterAlign';
    case 'right': return 'RightAlign';
    case 'justify': return 'JustifyAlign';
    default: return 'LeftAlign';
  }
}

function generateMimetype(): string {
  return 'application/vnd.adobe.indesign-idml-package';
}

function generateContainerXml(): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" conformance="Adobe IDML 1.0">
  <rootfile full-path="designmap.xml" media-type="application/vnd.adobe.indesign-idml-package+xml"/>
</container>`;
}

function generateDesignmapXml(storyIds: string[], spreadId: string): string {
  const storyRefs = storyIds.map(id => `    <idPkg:Story src="Stories/Story_${id}.xml"/>`).join('\n');

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Document xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="17.0">
  <RootStoryStyle Self="ParagraphStyle/$ID/NormalParagraphStyle" Name="$ID/NormalParagraphStyle"
    FontStyle="Regular" PointSize="12" Leading="14.4" Tracking="0"
    AppliedFont="Arial" HorizontalScale="100" VerticalScale="100"
    BasedOn="ParagraphStyle/$ID/[No paragraph style]" />
  <RootCharacterStyle Self="CharacterStyle/$ID/[No character style]" Name="$ID/[No character style]"
    AppliedFont="Arial" PointSize="12" />
  <RootTableStyle Self="TableStyle/$ID/[No table style]" Name="$ID/[No table style]" />
  <RootCellStyle Self="CellStyle/$ID/[No cell style]" Name="$ID/[No cell style]" />
  <RootFootnoteStyle Self="FootnoteStyle/$ID/Standard" Name="$ID/Standard" />
  <idPkg:Resources src="Resources/Styles.xml"/>
  <idPkg:Resources src="Resources/Fonts.xml"/>
  <idPkg:Resources src="Resources/Graphic.xml"/>
  <idPkg:Resources src="Resources/Preferences.xml"/>
  <idPkg:MasterSpreads src="MasterSpreads/MasterSpreads.xml"/>
  <idPkg:Spread src="Spreads/Spread_${spreadId}.xml"/>
${storyRefs}
  <idPkg:XML src="XML/BackingStory.xml"/>
  <idPkg:XML src="XML/Tags.xml"/>
  <idPkg:XML src="XML/Mapping.xml"/>
</Document>`;
}

function generateStylesXml(docxStyles: DocxStyle[]): string {
  let paragraphStyles = '';
  let characterStyles = '';

  // Default paragraph style
  paragraphStyles += `      <ParagraphStyle Self="ParagraphStyle/$ID/NormalParagraphStyle" Name="$ID/NormalParagraphStyle"
        FontStyle="Regular" PointSize="12" Leading="14.4" Tracking="0"
        AppliedFont="Arial" SpaceBefore="0" SpaceAfter="0"
        BasedOn="ParagraphStyle/$ID/[No paragraph style]" />
`;

  // Heading styles
  paragraphStyles += `      <ParagraphStyle Self="ParagraphStyle/Heading1" Name="Heading1"
        FontStyle="Bold" PointSize="24" Leading="28.8" Tracking="0"
        AppliedFont="Arial" SpaceBefore="12" SpaceAfter="6"
        BasedOn="ParagraphStyle/$ID/NormalParagraphStyle" />
`;
  paragraphStyles += `      <ParagraphStyle Self="ParagraphStyle/Heading2" Name="Heading2"
        FontStyle="Bold" PointSize="18" Leading="21.6" Tracking="0"
        AppliedFont="Arial" SpaceBefore="10" SpaceAfter="4"
        BasedOn="ParagraphStyle/$ID/NormalParagraphStyle" />
`;
  paragraphStyles += `      <ParagraphStyle Self="ParagraphStyle/Heading3" Name="Heading3"
        FontStyle="Bold" PointSize="14" Leading="16.8" Tracking="0"
        AppliedFont="Arial" SpaceBefore="8" SpaceAfter="4"
        BasedOn="ParagraphStyle/$ID/NormalParagraphStyle" />
`;
  paragraphStyles += `      <ParagraphStyle Self="ParagraphStyle/Title" Name="Title"
        FontStyle="Bold" PointSize="36" Leading="43.2" Tracking="0"
        AppliedFont="Arial" SpaceBefore="0" SpaceAfter="12"
        BasedOn="ParagraphStyle/$ID/NormalParagraphStyle" />
`;
  paragraphStyles += `      <ParagraphStyle Self="ParagraphStyle/Subtitle" Name="Subtitle"
        FontStyle="Italic" PointSize="16" Leading="19.2" Tracking="0"
        AppliedFont="Arial" SpaceBefore="0" SpaceAfter="8"
        BasedOn="ParagraphStyle/$ID/NormalParagraphStyle" />
`;
  paragraphStyles += `      <ParagraphStyle Self="ParagraphStyle/Quote" Name="Quote"
        FontStyle="Italic" PointSize="12" Leading="14.4" Tracking="0"
        AppliedFont="Arial" SpaceBefore="6" SpaceAfter="6"
        LeftIndent="36" RightIndent="36"
        BasedOn="ParagraphStyle/$ID/NormalParagraphStyle" />
`;
  paragraphStyles += `      <ParagraphStyle Self="ParagraphStyle/ListBullet" Name="ListBullet"
        FontStyle="Regular" PointSize="12" Leading="14.4" Tracking="0"
        AppliedFont="Arial" SpaceBefore="2" SpaceAfter="2"
        LeftIndent="36" FirstLineIndent="-18"
        BasedOn="ParagraphStyle/$ID/NormalParagraphStyle" />
`;
  paragraphStyles += `      <ParagraphStyle Self="ParagraphStyle/Code" Name="Code"
        FontStyle="Regular" PointSize="10" Leading="12" Tracking="0"
        AppliedFont="Courier New" SpaceBefore="4" SpaceAfter="4"
        BasedOn="ParagraphStyle/$ID/NormalParagraphStyle" />
`;

  // Map DOCX styles
  for (const style of docxStyles) {
    if (style.type === 'paragraph' && style.id !== 'Normal' && !style.id.startsWith('Default')) {
      const fontSize = style.fontSize || 12;
      const leading = fontSize * 1.2;
      const fontStyle = style.isBold ? 'Bold' : style.isItalic ? 'Italic' : 'Regular';
      const font = style.fontName || 'Arial';
      const basedOn = style.basedOn ? mapDocxStyleToIdml(style.basedOn) : 'ParagraphStyle/$ID/NormalParagraphStyle';

      paragraphStyles += `      <ParagraphStyle Self="ParagraphStyle/${escapeXml(style.name)}" Name="${escapeXml(style.name)}"
        FontStyle="${fontStyle}" PointSize="${fontSize}" Leading="${leading}" Tracking="0"
        AppliedFont="${escapeXml(font)}" SpaceBefore="0" SpaceAfter="0"
        BasedOn="${basedOn}" />
`;
    } else if (style.type === 'character') {
      const fontSize = style.fontSize || 12;
      const fontStyle = style.isBold ? 'Bold' : style.isItalic ? 'Italic' : 'Regular';
      const font = style.fontName || 'Arial';

      characterStyles += `      <CharacterStyle Self="CharacterStyle/${escapeXml(style.name)}" Name="${escapeXml(style.name)}"
        FontStyle="${fontStyle}" PointSize="${fontSize}"
        AppliedFont="${escapeXml(font)}" />
`;
    }
  }

  // Default character style
  characterStyles = `      <CharacterStyle Self="CharacterStyle/$ID/[No character style]" Name="$ID/[No character style]"
        FontStyle="Regular" PointSize="12"
        AppliedFont="Arial" />
` + characterStyles;

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Resources xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="17.0">
  <Styles>
    <ParagraphStyleRange>
${paragraphStyles}    </ParagraphStyleRange>
    <CharacterStyleRange>
${characterStyles}    </CharacterStyleRange>
    <ObjectStyleRange/>
    <TableStyleRange/>
    <CellStyleRange/>
    <TOCStyleRange/>
  </Styles>
</idPkg:Resources>`;
}

function generateFontsXml(fonts: Set<string>): string {
  const fontEntries = Array.from(fonts).map(font => {
    return `    <Font Self="Font/${escapeXml(font)}" Name="${escapeXml(font)}" FontFamily="${escapeXml(font)}"
      FontType="TrueType" Status="Available" />`;
  }).join('\n');

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Resources xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="17.0">
  <Fonts>
${fontEntries}
  </Fonts>
</idPkg:Resources>`;
}

function generateGraphicXml(): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Resources xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="17.0">
  <Colors>
    <Color Self="Color/Black" Name="Black" Model="Process" Space="CMYK"
      ColorValue="0 0 0 100" />
    <Color Self="Color/Paper" Name="Paper" Model="Process" Space="CMYK"
      ColorValue="0 0 0 0" />
    <Color Self="Color/Registration" Name="Registration" Model="Process" Space="CMYK"
      ColorValue="100 100 100 100" />
  </Colors>
  <Inks>
    <Ink Self="Ink/Black" Name="Black" />
    <Ink Self="Ink/Cyan" Name="Cyan" />
    <Ink Self="Ink/Magenta" Name="Magenta" />
    <Ink Self="Ink/Yellow" Name="Yellow" />
  </Inks>
  <Swatches/>
  <Gradients/>
  <StrokeStyles/>
</idPkg:Resources>`;
}

function generatePreferencesXml(): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Resources xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="17.0">
  <Preferences>
    <DocumentPreference PageWidth="612" PageHeight="792" PageOrientation="Portrait"
      AllowPageShuffle="true" AllowSpotColorMixing="false"
      FaceColumnCount="1" />
    <TextFramePreference AutoSizingType="HeightAndWidth"
      AutoSizingReferencePoint="TopLeftPoint" />
    <GridPreference BaselineDivision="1" BaselineStart="0"
      BaselineGridShown="false" DocumentGridShown="false" />
    <GuidePreference GuideColor="Cyan" GuidesShown="true"
      SnapToGuides="true" />
    <MarginPreference Top="72" Bottom="72" Left="72" Right="72"
      ColumnGutter="18" ColumnCount="1" />
  </Preferences>
</idPkg:Resources>`;
}

function generateMasterSpreadsXml(): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:MasterSpreads xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="17.0">
  <MasterSpread Self="uc" Name="A-Master" NamePrefix="A-"
    PageCount="1" ShowMasterItems="true"
    PageWidth="612" PageHeight="792" PageOrientation="Portrait"
    MarginTop="72" MarginBottom="72" MarginLeft="72" MarginRight="72"
    ColumnCount="1" ColumnGutter="18">
    <Properties>
      <PageTransform type="list">
        <Item type="record">
          <HorizontalTextFrameTransform type="array" />
        </Item>
      </PageTransform>
    </Properties>
  </MasterSpread>
</idPkg:MasterSpreads>`;
}

function generateSpreadXml(spreadId: string, textFrameIds: string[]): string {
  const textFrames = textFrameIds.map((frameId, index) => {
    const yPosition = 72 + (index * 720);
    return `    <TextFrame Self="${frameId}" ParentStory="${frameId}s" ContentType="TextType"
      ItemTransform="1 0 0 1 72 ${yPosition}">
      <Properties>
        <PathGeometry>
          <GeometryPathType PathOpen="false">
            <PathPointArray>
              <PathPointType Anchor="0 0" LeftDirection="0 0" RightDirection="0 0"/>
              <PathPointType Anchor="468 0" LeftDirection="468 0" RightDirection="468 0"/>
              <PathPointType Anchor="468 648" LeftDirection="468 648" RightDirection="468 648"/>
              <PathPointType Anchor="0 648" LeftDirection="0 648" RightDirection="0 648"/>
            </PathPointArray>
          </GeometryPathType>
        </PathGeometry>
      </Properties>
      <TextFramePreference AutoSizingType="HeightAndWidth" AutoSizingReferencePoint="TopLeftPoint" />
      <TextFrameContentAttribute TextType="TextType" />
    </TextFrame>`;
  }).join('\n');

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Spread xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="17.0">
  <Spread Self="${spreadId}" PageCount="1" BindingLocation="0"
    AllowPageShuffle="true" FlattenerOverride="Default"
    PageTransitionType="None" PageTransitionDirection="None"
    PageTransitionDuration="Medium">
    <Properties>
      <PageTransitionDuration type="enumeration">Medium</PageTransitionDuration>
      <PageTransitionDirection type="enumeration">Normal</PageTransitionDirection>
      <PageTransitionType type="enumeration">None</PageTransitionType>
    </Properties>
    <Page Self="p1" Name="1" AppliedMaster="uc"
      MasterPageTransform="1 0 0 1 0 0"
      PageColor="Black" PageBindingSide="LeftHand"
      PageWidth="612" PageHeight="792"
      MarginTop="72" MarginBottom="72" MarginLeft="72" MarginRight="72"
      AppliedTrapPreset="TrapPreset/$ID/kDefaultTrapStyleName">
      <Properties>
        <PageColor type="enumeration">None</PageColor>
      </Properties>
    </Page>
${textFrames}
  </Spread>
</idPkg:Spread>`;
}

function generateStoryXml(storyId: string, paragraphs: DocxParagraph[]): string {
  let paragraphRanges = '';

  for (const para of paragraphs) {
    const appliedStyle = mapDocxStyleToIdml(para.style);
    const alignment = getAlignmentValue(para.alignment);

    let charRanges = '';

    if (para.runs.length === 0) {
      // Empty paragraph - just add a break
      charRanges += `        <CharacterStyleRange AppliedCharacterStyle="CharacterStyle/$ID/[No character style]">
          <Content>${escapeXml(para.text) || '\uFEFF'}</Content>
        </CharacterStyleRange>
`;
    } else {
      for (const run of para.runs) {
        let charStyle = 'CharacterStyle/$ID/[No character style]';

        // Build character style attributes for local overrides
        let charAttrs = '';
        if (run.isBold) charAttrs += ' FontStyle="Bold"';
        if (run.isItalic) charAttrs += ' FontStyle="Italic"';
        if (run.fontSize) charAttrs += ` PointSize="${run.fontSize}"`;
        if (run.fontName) charAttrs += ` AppliedFont="${escapeXml(run.fontName)}"`;

        const content = escapeXml(run.text);

        charRanges += `        <CharacterStyleRange AppliedCharacterStyle="${charStyle}"${charAttrs}>
          <Content>${content}</Content>
        </CharacterStyleRange>
`;
      }
    }

    // Add paragraph break
    charRanges += `        <CharacterStyleRange AppliedCharacterStyle="CharacterStyle/$ID/[No character style]">
          <Br/>
        </CharacterStyleRange>
`;

    paragraphRanges += `      <ParagraphStyleRange AppliedParagraphStyle="${appliedStyle}" Justification="${alignment}">
${charRanges}      </ParagraphStyleRange>
`;
  }

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Story xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="17.0">
  <Story Self="${storyId}" UserText="true" IsEndnoteStory="false"
    AppliedTOCStyle="n" TrackChanges="false" StoryTitle="$ID/"
    AppliedNamedGrid="n">
    <StoryPreference OpticalMarginAlignment="false" OpticalMarginSize="12"
      FrameType="TextFrameType" StoryOrientation="Horizontal"
      StoryDirection="LeftToRightDirection"/>
    <InCopyExportOption IncludeGraphicProxies="true" IncludeAllResources="false"/>
${paragraphRanges}  </Story>
</idPkg:Story>`;
}

function generateBackingStoryXml(): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Story xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="17.0">
  <Story Self="ub0" AppliedTOCStyle="n" TrackChanges="false" StoryTitle="$ID/" AppliedNamedGrid="n">
    <StoryPreference OpticalMarginAlignment="false" OpticalMarginSize="12"
      FrameType="TextFrameType" StoryOrientation="Horizontal"
      StoryDirection="LeftToRightDirection"/>
    <InCopyExportOption IncludeGraphicProxies="true" IncludeAllResources="false"/>
    <ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/$ID/NormalParagraphStyle">
      <CharacterStyleRange AppliedCharacterStyle="CharacterStyle/$ID/[No character style]">
        <Content/>
      </CharacterStyleRange>
    </ParagraphStyleRange>
  </Story>
</idPkg:Story>`;
}

function generateTagsXml(): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:XML xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="17.0">
  <XMLTags>
    <XMLTag Self="XMLTag/Document" TagName="Document" />
    <XMLTag Self="XMLTag/Paragraph" TagName="Paragraph" />
    <XMLTag Self="XMLTag/Heading1" TagName="Heading1" />
    <XMLTag Self="XMLTag/Heading2" TagName="Heading2" />
  </XMLTags>
</idPkg:XML>`;
}

function generateMappingXml(): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:XML xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="17.0">
  <XMLImportMap>
    <XMLImportMapElement Self="XMLImportMapElement/Document" MappedStyle="ParagraphStyle/$ID/NormalParagraphStyle">
      <MarkupTag Self="XMLTag/Document" />
    </XMLImportMapElement>
    <XMLImportMapElement Self="XMLImportMapElement/Paragraph" MappedStyle="ParagraphStyle/$ID/NormalParagraphStyle">
      <MarkupTag Self="XMLTag/Paragraph" />
    </XMLImportMapElement>
  </XMLImportMap>
</idPkg:XML>`;
}

// Split paragraphs into chunks for multiple text frames
function splitIntoChunks(paragraphs: DocxParagraph[], maxPerFrame: number = 50): DocxParagraph[][] {
  const chunks: DocxParagraph[][] = [];
  for (let i = 0; i < paragraphs.length; i += maxPerFrame) {
    chunks.push(paragraphs.slice(i, i + maxPerFrame));
  }
  if (chunks.length === 0) {
    chunks.push([{
      text: '',
      style: 'Normal',
      isBold: false,
      isItalic: false,
      isUnderline: false,
      fontSize: null,
      fontName: null,
      alignment: 'left',
      runs: [],
    }]);
  }
  return chunks;
}

export async function generateIdml(docxContent: DocxContent): Promise<Blob> {
  idCounter = 100; // Reset counter
  const zip = new JSZip();

  // Split paragraphs into chunks for multiple text frames
  const chunks = splitIntoChunks(docxContent.paragraphs);

  // Generate story IDs and frame IDs
  const storyIds: string[] = [];
  const textFrameIds: string[] = [];

  for (let i = 0; i < chunks.length; i++) {
    const storyId = nextId();
    const frameId = nextId();
    storyIds.push(storyId);
    textFrameIds.push(frameId);
  }

  const spreadId = nextId();

  // Add mimetype (must be first, uncompressed)
  zip.file('mimetype', generateMimetype(), { compression: 'STORE' });

  // Add META-INF
  zip.folder('META-INF')?.file('container.xml', generateContainerXml());

  // Add designmap.xml
  zip.file('designmap.xml', generateDesignmapXml(storyIds, spreadId));

  // Add Resources
  const resourcesFolder = zip.folder('Resources');
  resourcesFolder?.file('Styles.xml', generateStylesXml(docxContent.styles));
  resourcesFolder?.file('Fonts.xml', generateFontsXml(docxContent.fonts));
  resourcesFolder?.file('Graphic.xml', generateGraphicXml());
  resourcesFolder?.file('Preferences.xml', generatePreferencesXml());

  // Add MasterSpreads
  zip.folder('MasterSpreads')?.file('MasterSpreads.xml', generateMasterSpreadsXml());

  // Add Spreads
  zip.folder('Spreads')?.file(`Spread_${spreadId}.xml`, generateSpreadXml(spreadId, textFrameIds));

  // Add Stories
  const storiesFolder = zip.folder('Stories');
  for (let i = 0; i < chunks.length; i++) {
    storiesFolder?.file(`Story_${storyIds[i]}.xml`, generateStoryXml(storyIds[i], chunks[i]));
  }

  // Add XML folder
  const xmlFolder = zip.folder('XML');
  xmlFolder?.file('BackingStory.xml', generateBackingStoryXml());
  xmlFolder?.file('Tags.xml', generateTagsXml());
  xmlFolder?.file('Mapping.xml', generateMappingXml());

  // Generate the ZIP blob
  const blob = await zip.generateAsync({
    type: 'blob',
    mimeType: 'application/vnd.adobe.indesign-idml-package',
    compression: 'DEFLATE',
    compressionOptions: { level: 9 },
  });

  return blob;
}

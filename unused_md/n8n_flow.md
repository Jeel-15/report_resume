{
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "generate-report",
        "responseMode": "responseNode",
        "options": {}
      },
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2.1,
      "position": [
        0,
        0
      ],
      "id": "aa1772a6-b03a-4151-a9c1-8a3c215a1c54",
      "name": "Webhook",
      "webhookId": "6d3c79ea-a236-4737-a6ff-97808cc84e2d"
    },
    {
      "parameters": {
        "jsCode": "const body = $input.first().json.body;\n\nif (!body) throw new Error('Request body is missing');\nif (!body.student) throw new Error('Missing: body.student');\nif (!body.college) throw new Error('Missing: body.college');\nif (!body.university) throw new Error('Missing: body.university');\nif (!body.reportConfig) throw new Error('Missing: body.reportConfig');\nif (body.reportConfig.sections !== undefined && !Array.isArray(body.reportConfig.sections)) {\n  throw new Error('reportConfig.sections must be an array if provided');\n}\n\nconst student = body.student;\nconst college = body.college;\nconst university = body.university;\nconst industry = body.industry || {};\nconst internship = body.internship || {};\nconst config = body.reportConfig || {};\nconst policy = config.policy || {};\n\nconst reportId = body.reportId;\nconst callbackUrl = body.callbackUrl;\n\nconst rawLanguage = String(config.language || 'English').trim();\nconst dynamicInstruction = String(policy.generationInstruction || '').trim();\nconst strictLanguageOnly = policy.strictLanguageOnly === true;\nconst langKey = rawLanguage.toLowerCase().replace(/\\s+/g, '_');\n\nconst langInstr = dynamicInstruction || [\n  `Write in ${rawLanguage}.`,\n  strictLanguageOnly\n    ? 'Strict rule: Use only the target language/script. Do not mix other languages except unavoidable proper nouns.'\n    : 'Keep language natural and professional for academic report writing.',\n  'Do not use markdown formatting in output.',\n].join(' ');\n\n// ── Build format permission flags from config ──\nconst contentType = String(config.contentType || '').toLowerCase();\nconst genInstr = String(policy.generationInstruction || '').toLowerCase();\nconst allowTables   = (contentType.includes('table') || genInstr.includes('table'))   ? 'YES' : 'NO';\nconst allowBullets  = genInstr.includes('no bullet')   ? 'NO' : 'YES';\nconst allowSubtitles = genInstr.includes('no subtitle') ? 'NO' : 'YES';\n\n// ── Auto-generate key from title if key is missing ──\nconst safeSections = (config.sections || [])\n  .filter(s => s && s.title)\n  .map(s => ({\n    ...s,\n    key: s.key || s.title.toLowerCase().replace(/\\s+/g, '_').replace(/[^a-z0-9_]/g, '')\n  }));\n\nconst defaultSections = [\n  { key: 'acknowledgement',  title: 'Acknowledgement',             description: 'Thanks to mentors, institution, and supporters.' },\n  { key: 'abstract',         title: 'Abstract',                    description: 'Summary of internship, activities, and outcomes.' },\n  { key: 'introduction',     title: 'Introduction',                description: 'Background, objectives, and scope of internship.' },\n  { key: 'workDescription',  title: 'Work Description & Activities', description: 'Detailed tasks, tools, process, and execution.' },\n  { key: 'learningOutcomes', title: 'Learning Outcomes',           description: 'Skills, knowledge, and competencies gained.' },\n  { key: 'conclusion',       title: 'Conclusion & Recommendations', description: 'Summary, reflections, and recommendations.' },\n  { key: 'references',       title: 'References',                  description: 'Books, websites, papers, and other sources.' },\n];\n\nconst sectionsToUse = safeSections.length ? safeSections : defaultSections;\nif (!sectionsToUse.length) {\n  throw new Error('No sections available. Please configure reportSections in the Major admin panel.');\n}\n\nconst context = [\n  `STUDENT: ${student.name} (Roll: ${student.rollNumber || 'N/A'}, Email: ${student.email || 'N/A'})`,\n  `COLLEGE: ${college.name || 'N/A'}`,\n  `UNIVERSITY: ${university.name || 'N/A'}`,\n  `COMPANY: ${industry.name || 'N/A'}`,\n  `PROJECT: ${internship.projectTitle || 'N/A'}`,\n  `INTERNSHIP TITLE: ${internship.internshipTitle || 'N/A'}`,\n  `DURATION: ${internship.duration || 'N/A'} (${internship.startDate || ''} to ${internship.endDate || ''})`,\n  `SKILLS: ${internship.keySkills || 'N/A'}`,\n  '',\n  'WHAT STUDENT DID:',\n  internship.briefDescription || '',\n].join('\\n');\n\nconst items = sectionsToUse.map((section, index) => {\n  const isAbstract = section.key === 'abstract';\n\n  const sectionSpecificPrompt = [\n    `Write the \"${section.title}\" section.`,\n    `Description: ${section.description || section.title}`,\n    isAbstract\n      ? 'Use THIRD PERSON for abstract. Write as flowing prose only. No bullets. No bold paragraphs.'\n      : 'Use FIRST PERSON. Do not mention student by name. Use \"I\".',\n    'Length: 280-420 words.',\n  ].join('\\n');\n\n  const fullPrompt = [\n    'You are writing ONE section of an academic internship report.',\n    `The student ${student.name || 'Student'} is the author. Write AS the student unless section asks otherwise.`,\n    '',\n    langInstr,\n    '',\n    'CONTEXT:',\n    context,\n    '',\n    '=== RETURN FORMAT (MUST BE VALID JSON) ===',\n    'Return ONLY a JSON object with exactly these keys: sectionTitle, sectionContent, uiLabels, references',\n    '- references: array of {title: string, url: string} for sources of any factual claims. Empty array if none.',\n    '',\n    '=== FORMATTING RULES ===',\n    'Return sectionContent as plain text with optional structural tags only when truly needed.',\n    '',\n    'AVAILABLE TAGS:',\n    '[TABLE_START]',\n    'RealHeader1|RealHeader2|RealHeader3',\n    'Value1|Value2|Value3',\n    '[TABLE_END]',\n    '',\n    '[BULLET_START]',\n    '- First point',\n    '- Second point',\n    '[BULLET_END]',\n    '',\n    '[SUBTITLE]Heading text here[/SUBTITLE]',\n    '[SUBPOINT]Indented sub-paragraph here[/SUBPOINT]',\n    '[BOLD]key phrase[/BOLD]',\n    '',\n    'STRICT RULES — NEVER VIOLATE:',\n    '- The section heading is already printed by the PDF template. NEVER repeat the section title at the start of sectionContent.',\n    '- NEVER open sectionContent with [SUBTITLE] that mirrors the section title.',\n    '- [BOLD] applies only to 2–5 word key phrases. NEVER bold a full sentence or paragraph.',\n    '- NEVER output placeholder column headers like Col1, Col2, Col3, HeaderA, HeaderB.',\n    '- NEVER create a table unless you have REAL named columns with REAL comparable row data.',\n    '- If tabular data does not exist, use [BULLET_START] list instead of a table.',\n    '- Do NOT force bullets or subtitles into naturally flowing prose sections.',\n    '- No markdown (no **, no #, no -).',\n    '- Formulas may use LaTeX delimiters \\\\( \\\\) or \\\\[ \\\\].',\n    `- Tables allowed: ${allowTables}. Bullets allowed: ${allowBullets}. Subtitles allowed: ${allowSubtitles}.`,\n    'PLAGIARISM PREVENTION RULES (MANDATORY):',\n    '- Do NOT copy-paste any text from the internet or known sources.',\n    '- Paraphrase all facts, definitions, and concepts in your own words.',\n    '- Do not include long quoted lines. If quoting is needed, keep it under 10 words and use quotation marks.',\n    '- Add a references field in your JSON response: an array of objects with {title, url} for any factual claims.',\n    '- Write originally. Similarity to existing web content must be below 5% per source.',\n    '',\n    '',\n    '=== SECTION TO WRITE ===',\n    `Section: \"${section.title}\"`,\n    '',\n    sectionSpecificPrompt,\n  ].join('\\n');\n\n  return {\n    json: {\n      prompt: fullPrompt,\n      sectionKey: section.key,\n      sectionTitle: section.title,\n      sectionIndex: index,\n      totalSections: sectionsToUse.length,\n      reportId,\n      callbackUrl,\n      configLanguage: rawLanguage,\n      strictLanguageOnly,\n      langKey,\n    }\n  };\n});\n\nreturn items;\n\n// const body = $input.first().json.body;\n\n// if (!body) throw new Error('Request body is missing');\n// if (!body.student) throw new Error('Missing: body.student');\n// if (!body.college) throw new Error('Missing: body.college');\n// if (!body.university) throw new Error('Missing: body.university');\n// if (!body.reportConfig) throw new Error('Missing: body.reportConfig');\n// if (body.reportConfig.sections !== undefined && !Array.isArray(body.reportConfig.sections)) {\n//   throw new Error('reportConfig.sections must be an array if provided');\n// }\n\n// const student = body.student;\n// const college = body.college;\n// const university = body.university;\n// const industry = body.industry || {};\n// const internship = body.internship || {};\n// const config = body.reportConfig || {};\n// const policy = config.policy || {};\n\n// const reportId = body.reportId;\n// const callbackUrl = body.callbackUrl;\n\n// const rawLanguage = String(config.language || 'English').trim();\n// const dynamicInstruction = String(policy.generationInstruction || '').trim();\n// const strictLanguageOnly = policy.strictLanguageOnly === true;\n// const langKey = rawLanguage.toLowerCase().replace(/\\s+/g, '_');\n\n// const langInstr = dynamicInstruction || [\n//   `Write in ${rawLanguage}.`,\n//   strictLanguageOnly\n//     ? 'Strict rule: Use only the target language/script. Do not mix other languages except unavoidable proper nouns.'\n//     : 'Keep language natural and professional for academic report writing.',\n//   'Do not use markdown formatting in output.',\n// ].join(' ');\n\n// const safeSections = (config.sections || []).filter(s => s && s.key && s.title);\n// const defaultSections = [\n//   { key: 'acknowledgement', title: 'Acknowledgement', description: 'Thanks to mentors, institution, and supporters.' },\n//   { key: 'abstract', title: 'Abstract', description: 'Summary of internship, activities, and outcomes.' },\n//   { key: 'introduction', title: 'Introduction', description: 'Background, objectives, and scope of internship.' },\n//   { key: 'workDescription', title: 'Work Description & Activities', description: 'Detailed tasks, tools, process, and execution.' },\n//   { key: 'learningOutcomes', title: 'Learning Outcomes', description: 'Skills, knowledge, and competencies gained.' },\n//   { key: 'conclusion', title: 'Conclusion & Recommendations', description: 'Summary, reflections, and recommendations.' },\n//   { key: 'references', title: 'References', description: 'Books, websites, papers, and other sources.' },\n// ];\n\n// const sectionsToUse = safeSections.length ? safeSections : defaultSections;\n// if (!sectionsToUse.length) {\n//   throw new Error('No sections available. Please configure reportSections in the Major admin panel.');\n// }\n\n// const context = [\n//   `STUDENT: ${student.name} (Roll: ${student.rollNumber || 'N/A'}, Email: ${student.email || 'N/A'})`,\n//   `COLLEGE: ${college.name || 'N/A'}`,\n//   `UNIVERSITY: ${university.name || 'N/A'}`,\n//   `COMPANY: ${industry.name || 'N/A'}`,\n//   `PROJECT: ${internship.projectTitle || 'N/A'}`,\n//   `INTERNSHIP TITLE: ${internship.internshipTitle || 'N/A'}`,\n//   `DURATION: ${internship.duration || 'N/A'} (${internship.startDate || ''} to ${internship.endDate || ''})`,\n//   `SKILLS: ${internship.keySkills || 'N/A'}`,\n//   '',\n//   'WHAT STUDENT DID:',\n//   internship.briefDescription || '',\n// ].join('\\n');\n\n// const items = sectionsToUse.map((section, index) => {\n//   const sectionSpecificPrompt = [\n//     `Write the \\\"${section.title}\\\" section.`,\n//     `Description: ${section.description || section.title}`,\n//     section.key === 'abstract'\n//       ? 'Use THIRD PERSON for abstract.'\n//       : 'Use FIRST PERSON. Do not mention student by name. Use \\\"I\\\".',\n//     'Length: 280-420 words.',\n//   ].join('\\n');\n\n//   const fullPrompt = [\n//     'You are writing ONE section of an academic internship report.',\n//     `The student ${student.name || 'Student'} is the author. Write AS the student unless section asks otherwise.`,\n//     '',\n//     langInstr,\n//     '',\n//     'CONTEXT:',\n//     context,\n//     '',\n//     '=== RETURN FORMAT (MUST BE VALID JSON) ===',\n//     'Return ONLY a JSON object with: sectionTitle, sectionContent, uiLabels',\n//     '=== FORMATTING RULES (MANDATORY) ===',\n//     'You MUST use these exact tags whenever applicable (according to {config} data) :',\n//     '',\n//     '[TABLE_START]',\n//     'Col1|Col2|Col3',\n//     'Row1Val1|Row1Val2|Row1Val3',\n//     '[TABLE_END]',\n//     '',\n//     '[BULLET_START]',\n//     '- First point',\n//     '- Second point',\n//     '[BULLET_END]',\n//     '',\n//     '[SUBTITLE]Section heading here[/SUBTITLE]',\n//     '',\n//     '[SUBPOINT]Indented sub-paragraph text here[/SUBPOINT]',\n//     '',\n//     '[BOLD]important word or phrase[/BOLD]',\n//     '',\n//     'These tags are REQUIRED. If admin instructions mention a table, use [TABLE_START]. If there are lists, use [BULLET_START]. Do not use markdown like ** or - instead of these tags.',\n//     'Plain text with no special formatting needs no tags.',\n//     'formulas may use LaTeX delimiters \\\\( \\\\) or \\\\[ \\\\].',\n//     '',\n//     '=== SECTION TO WRITE ===',\n//     `Section: \\\"${section.title}\\\"`,\n//     '',\n//     sectionSpecificPrompt,\n//   ].join('\\n');\n\n//   return {\n//     json: {\n//       prompt: fullPrompt,\n//       sectionKey: section.key,\n//       sectionTitle: section.title,\n//       sectionIndex: index,\n//       totalSections: sectionsToUse.length,\n//       reportId,\n//       callbackUrl,\n//       configLanguage: rawLanguage,\n//       strictLanguageOnly,\n//       langKey,\n//     }\n//   };\n// });\n\n// return items;"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [
        208,
        0
      ],
      "id": "c5ca8593-344a-4e94-a68f-213cd6baab8b",
      "name": "Split Into Sections"
    },
    {
      "parameters": {
        "modelId": {
          "__rl": true,
          "value": "gpt-4.1",
          "mode": "list",
          "cachedResultName": "GPT-4.1"
        },
        "responses": {
          "values": [
            {
              "content": "={{ $json.prompt }}"
            }
          ]
        },
        "builtInTools": {},
        "options": {}
      },
      "type": "@n8n/n8n-nodes-langchain.openAi",
      "typeVersion": 2.1,
      "position": [
        416,
        0
      ],
      "id": "552c2e92-c344-491b-9fff-4b871ea1b07e",
      "name": "Generate Section",
      "credentials": {
        "openAiApi": {
          "id": "6e6toRD2gTQta9D9",
          "name": "OpenAi report_gen"
        }
      }
    },
    {
      "parameters": {
        "jsCode": "const allItems = $input.all();\nconst splitItems = $('Split Into Sections').all();\n\nconst generatedReferences = {};\nconst generatedContent = {};\nconst generatedTitles = {};\nlet generatedUiLabels = {};\n\nconst reportId = splitItems[0]?.json.reportId || '';\nconst callbackUrl = splitItems[0]?.json.callbackUrl || '';\nconst expectedCount = splitItems.length;\n\nif (!reportId) throw new Error('Missing reportId from Split node');\nif (!callbackUrl) throw new Error('Missing callbackUrl from Split node');\n\nconst firstMeta = splitItems[0]?.json || {};\nconst configLanguage = String(firstMeta.configLanguage || 'English');\nconst langKey = String(firstMeta.langKey || 'english');\nconst strictLanguageOnly = firstMeta.strictLanguageOnly === true;\n\nconst indexToKey = {};\nconst indexToTitle = {};\nfor (let i = 0; i < splitItems.length; i++) {\n  indexToKey[i] = splitItems[i].json.sectionKey || '';\n  indexToTitle[i] = splitItems[i].json.sectionTitle || '';\n}\n\nfunction stripCodeFences(text) {\n  return String(text || '')\n    .replace(/^```json\\s*/i, '')\n    .replace(/^```\\s*/i, '')\n    .replace(/```\\s*$/i, '')\n    .trim();\n}\n\nfunction extractJsonObjectText(text) {\n  const t = String(text || '');\n  const start = t.indexOf('{');\n  const end = t.lastIndexOf('}');\n  if (start === -1 || end === -1 || end <= start) return t;\n  return t.slice(start, end + 1);\n}\n\nfunction parseSectionPayload(rawText) {\n  const cleaned = stripCodeFences(rawText);\n  const slice = extractJsonObjectText(cleaned);\n  const candidates = [cleaned, slice];\n  for (const c of candidates) {\n    try {\n      const obj = JSON.parse(c);\n      if (obj && typeof obj === 'object') return obj;\n    } catch (_) {}\n  }\n  throw new Error('Unable to parse AI JSON response');\n}\n\nfunction extractAiText(data) {\n  if (Array.isArray(data.output)) {\n    const firstMsg = data.output[0];\n    if (firstMsg && Array.isArray(firstMsg.content)) {\n      return firstMsg.content\n        .filter(c => c && typeof c.text === 'string')\n        .map(c => c.text)\n        .join('\\n')\n        .trim();\n    }\n  }\n  if (Array.isArray(data.content)) {\n    return data.content\n      .filter(c => c && typeof c.text === 'string')\n      .map(c => c.text)\n      .join('\\n')\n      .trim();\n  }\n  if (typeof data.output === 'string') return data.output;\n  if (data.message?.content) return data.message.content;\n  if (data.choices?.[0]?.message?.content) return data.choices[0].message.content;\n  if (typeof data.text === 'string') return data.text;\n  return '';\n}\n\nfunction hasInvalidScript(text) {\n  if (!strictLanguageOnly || langKey === 'english') return false;\n  let cleaned = String(text || '');\n  cleaned = cleaned.replace(/\\\\\\[[\\s\\S]*?\\\\\\]/g, ' ');\n  cleaned = cleaned.replace(/\\\\\\([\\s\\S]*?\\\\\\)/g, ' ');\n  cleaned = cleaned.replace(/\\\\[A-Za-z]+/g, ' ');\n  cleaned = cleaned.replace(/[{}_^]/g, ' ');\n  const latinWords = cleaned.match(/\\b[A-Za-z]{4,}\\b/g) || [];\n  return latinWords.length > 8;\n}\n\nfor (let i = 0; i < allItems.length; i++) {\n  const data = allItems[i].json;\n  const sectionKey = indexToKey[i] || '';\n  const sectionTitle = indexToTitle[i] || sectionKey;\n\n  const aiJsonText = extractAiText(data);\n  let parsed;\n  try {\n    parsed = parseSectionPayload(aiJsonText);\n  } catch (e) {\n    throw new Error(`Failed to parse section \"${sectionTitle}\": ${e.message}`);\n  }\n\n  const aiTitle = String(parsed.sectionTitle || '').trim() || sectionTitle;\n  const aiContent = String(parsed.sectionContent || '').trim();\n  const aiReferences = Array.isArray(parsed.references) ? parsed.references : [];\n  const aiUiLabels = parsed.uiLabels && typeof parsed.uiLabels === 'object' ? parsed.uiLabels : null;\n\n  if (!aiContent) throw new Error(`Empty content returned for section \"${sectionTitle}\"`);\n  if (hasInvalidScript(aiContent)) {\n    throw new Error(`Language policy violated in section \"${sectionTitle}\" for language \"${configLanguage}\"`);\n  }\n\n  if (sectionKey) {\n    generatedContent[sectionKey] = aiContent;\n    generatedReferences[sectionKey] = aiReferences;\n    generatedTitles[sectionKey] = aiTitle;\n    if (aiUiLabels && Object.keys(aiUiLabels).length > Object.keys(generatedUiLabels).length) {\n      generatedUiLabels = aiUiLabels;\n    }\n  }\n}\n\nconst actualCount = Object.keys(generatedContent).length;\nif (actualCount < expectedCount) {\n  throw new Error(`Incomplete: expected ${expectedCount} sections, got ${actualCount}`);\n}\n\n// ── Internal duplicate sentence check ──\nconst allSentences = [];\nfor (const key of Object.keys(generatedContent)) {\n  const sentences = generatedContent[key]\n    .split(/[.!?]+/)\n    .map(s => s.trim().toLowerCase())\n    .filter(s => s.length > 30);\n  allSentences.push(...sentences.map(s => ({ sentence: s, key })));\n}\nconst seen = {};\nfor (const { sentence, key } of allSentences) {\n  if (seen[sentence]) {\n    throw new Error(`Duplicate sentence detected across sections \"${seen[sentence]}\" and \"${key}\". Possible plagiarism risk.`);\n  }\n  seen[sentence] = key;\n}\n\n// ── Build ordered section list for backend TOC rendering ──\nconst orderedSections = Object.keys(indexToKey)\n  .sort((a, b) => Number(a) - Number(b))\n  .map(i => ({\n    index: Number(i),\n    key: indexToKey[i],\n    title: generatedTitles[indexToKey[i]] || indexToTitle[i],\n    content: generatedContent[indexToKey[i]] || '',\n  }));\n\nreturn [{\n  json: {\n    reportId,\n    callbackUrl,\n    generatedContent,\n    generatedTitles,\n    generatedUiLabels,\n    generatedReferences,\n    orderedSections,\n    sectionCount: actualCount,\n  }\n}];\n\n\n// const allItems = $input.all();\n// const splitItems = $('Split Into Sections').all();\n\n// const generatedContent = {};\n// const generatedTitles = {};\n// let generatedUiLabels = {};\n\n// const reportId = splitItems[0]?.json.reportId || '';\n// const callbackUrl = splitItems[0]?.json.callbackUrl || '';\n// const expectedCount = splitItems.length;\n\n// if (!reportId) throw new Error('Missing reportId from Split node');\n// if (!callbackUrl) throw new Error('Missing callbackUrl from Split node');\n\n// const firstMeta = splitItems[0]?.json || {};\n// const configLanguage = String(firstMeta.configLanguage || 'English');\n// const langKey = String(firstMeta.langKey || 'english');\n// const strictLanguageOnly = firstMeta.strictLanguageOnly === true;\n\n// const indexToKey = {};\n// const indexToTitle = {};\n// for (let i = 0; i < splitItems.length; i++) {\n//   indexToKey[i] = splitItems[i].json.sectionKey || '';\n//   indexToTitle[i] = splitItems[i].json.sectionTitle || '';\n// }\n\n// function stripCodeFences(text) {\n//   return String(text || '')\n//     .replace(/^```json\\s*/i, '')\n//     .replace(/^```\\s*/i, '')\n//     .replace(/```\\s*$/i, '')\n//     .trim();\n// }\n\n// function extractJsonObjectText(text) {\n//   const t = String(text || '');\n//   const start = t.indexOf('{');\n//   const end = t.lastIndexOf('}');\n//   if (start === -1 || end === -1 || end <= start) return t;\n//   return t.slice(start, end + 1);\n// }\n\n// function parseSectionPayload(rawText) {\n//   const cleaned = stripCodeFences(rawText);\n//   const slice = extractJsonObjectText(cleaned);\n//   const candidates = [cleaned, slice];\n//   for (const c of candidates) {\n//     try {\n//       const obj = JSON.parse(c);\n//       if (obj && typeof obj === 'object') return obj;\n//     } catch (_) {}\n//   }\n//   throw new Error('Unable to parse AI JSON response');\n// }\n\n// function extractAiText(data) {\n//   if (Array.isArray(data.output)) {\n//     const firstMsg = data.output[0];\n//     if (firstMsg && Array.isArray(firstMsg.content)) {\n//       return firstMsg.content\n//         .filter(c => c && typeof c.text === 'string')\n//         .map(c => c.text)\n//         .join('\\n')\n//         .trim();\n//     }\n//   }\n//   if (Array.isArray(data.content)) {\n//     return data.content\n//       .filter(c => c && typeof c.text === 'string')\n//       .map(c => c.text)\n//       .join('\\n')\n//       .trim();\n//   }\n//   if (typeof data.output === 'string') return data.output;\n//   if (data.message?.content) return data.message.content;\n//   if (data.choices?.[0]?.message?.content) return data.choices[0].message.content;\n//   if (typeof data.text === 'string') return data.text;\n//   return '';\n// }\n\n// function hasInvalidScript(text) {\n//   if (!strictLanguageOnly || langKey === 'english') return false;\n//   let cleaned = String(text || '');\n//   cleaned = cleaned.replace(/\\\\\\[[\\s\\S]*?\\\\\\]/g, ' ');\n//   cleaned = cleaned.replace(/\\\\\\([\\s\\S]*?\\\\\\)/g, ' ');\n//   cleaned = cleaned.replace(/\\\\[A-Za-z]+/g, ' ');\n//   cleaned = cleaned.replace(/[{}_^]/g, ' ');\n//   const latinWords = cleaned.match(/\\b[A-Za-z]{4,}\\b/g) || [];\n//   return latinWords.length > 8;\n// }\n\n// for (let i = 0; i < allItems.length; i++) {\n//   const data = allItems[i].json;\n//   const sectionKey = indexToKey[i] || '';\n//   const sectionTitle = indexToTitle[i] || sectionKey;\n\n//   const aiJsonText = extractAiText(data);\n//   let parsed;\n//   try {\n//     parsed = parseSectionPayload(aiJsonText);\n//   } catch (e) {\n//     throw new Error(`Failed to parse section \\\"${sectionTitle}\\\": ${e.message}`);\n//   }\n\n//   const aiTitle = String(parsed.sectionTitle || '').trim() || sectionTitle;\n//   const aiContent = String(parsed.sectionContent || '').trim();\n//   const aiUiLabels = parsed.uiLabels && typeof parsed.uiLabels === 'object' ? parsed.uiLabels : null;\n\n//   if (!aiContent) throw new Error(`Empty content returned for section \\\"${sectionTitle}\\\"`);\n//   if (hasInvalidScript(aiContent)) {\n//     throw new Error(`Language policy violated in section \\\"${sectionTitle}\\\" for language \\\"${configLanguage}\\\"`);\n//   }\n\n//   if (sectionKey) {\n//     generatedContent[sectionKey] = aiContent;\n//     generatedTitles[sectionKey] = aiTitle;\n//     if (aiUiLabels && Object.keys(aiUiLabels).length > Object.keys(generatedUiLabels).length) {\n//       generatedUiLabels = aiUiLabels;\n//     }\n//   }\n// }\n\n// const actualCount = Object.keys(generatedContent).length;\n// if (actualCount < expectedCount) {\n//   throw new Error(`Incomplete: expected ${expectedCount} sections, got ${actualCount}`);\n// }\n\n// return [{\n//   json: {\n//     reportId,\n//     callbackUrl,\n//     generatedContent,\n//     generatedTitles,\n//     generatedUiLabels,\n//     sectionCount: actualCount,\n//   }\n// }];"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [
        768,
        0
      ],
      "id": "e6918f11-7fd8-4bf0-92af-77f091368201",
      "name": "Merge All Sections"
    },
    {
      "parameters": {
        "method": "PUT",
        "url": "={{ $json.callbackUrl }}",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "Content-Type",
              "value": "application/json"
            },
            {
              "name": "X-Callback-Secret",
              "value": "OYDEp7Q3hWgLjJQHFopG_c8mFJ7WyaqO1cp3VckSup71iMVhMlF80Nt8q9EY1Hbr"
            }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ $json }}",
        "options": {}
      },
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.3,
      "position": [
        1024,
        0
      ],
      "id": "087f72db-53ee-4583-bfdf-20ee37e77239",
      "name": "Send to Backend1"
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "{\n  \"success\": true,\n  \"message\": \"Report generated section by section\"\n}",
        "options": {}
      },
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1.4,
      "position": [
        1248,
        0
      ],
      "id": "c7dbb060-e455-4f70-93f8-6ba0f0e21099",
      "name": "Respond Ok"
    }
  ],
  "connections": {
    "Webhook": {
      "main": [
        [
          {
            "node": "Split Into Sections",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Split Into Sections": {
      "main": [
        [
          {
            "node": "Generate Section",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Generate Section": {
      "main": [
        [
          {
            "node": "Merge All Sections",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Merge All Sections": {
      "main": [
        [
          {
            "node": "Send to Backend1",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Send to Backend1": {
      "main": [
        [
          {
            "node": "Respond Ok",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  },
  "pinData": {
    "Webhook": [
      {
        "headers": {
          "connection": "Keep-Alive",
          "content-type": "application/json",
          "accept": "*/*",
          "accept-encoding": "gzip, deflate",
          "host": "ai.ivinfotech.com",
          "max-forwards": "10",
          "user-agent": "python-requests/2.31.0",
          "x-original-url": "/webhook/generate-report",
          "x-forwarded-for": "103.159.201.109:54989",
          "x-arr-ssl": "2048|256|C=US, O=Let's Encrypt, CN=R12|CN=ai.ivinfotech.com",
          "x-arr-log-id": "39247881-89de-4554-a935-cfe161dca9ca",
          "content-length": "3459"
        },
        "params": {},
        "query": {},
        "body": {
          "reportId": "69c21e71a902977644e80994",
          "callbackUrl": "https://yadira-unbeached-semijocularly.ngrok-free.dev//api/reports/69c21e71a902977644e80994/generated",
          "student": {
            "name": "Jeel",
            "email": "jeel@gmail.com",
            "rollNumber": "21bt04078",
            "enrollmentNumber": "21bt04078",
            "villageCityName": "Vadodara",
            "district": "Vadodara",
            "state": "Gujarat"
          },
          "college": {
            "name": "",
            "villageCityName": "",
            "district": "",
            "state": "",
            "website": ""
          },
          "university": {
            "name": "GSFC University",
            "villageCityName": "",
            "district": "",
            "state": ""
          },
          "industry": {
            "name": "IVInfotech",
            "villageCityName": "",
            "district": "",
            "state": "",
            "website": "",
            "supervisorName": "Hardik"
          },
          "academic": {
            "degree": "Commerce",
            "major": "BCOM Accounting",
            "university": "GSFC University",
            "college": "",
            "collegeCity": "",
            "collegeState": ""
          },
          "internship": {
            "industryName": "IVInfotech",
            "industryCity": "",
            "industryState": "",
            "industryWebsite": "",
            "supervisorName": "Hardik",
            "supervisorContact": "Hardik",
            "projectTitle": "A Study of Accounting Systems and Internal Control Mechanisms",
            "internshipTitle": "recorded, verified, and analyzed in a professional environment.",
            "academicYear": "2025-2026",
            "duration": "6 weeks",
            "startDate": "2026-02-17",
            "endDate": "2026-03-24",
            "positionTitle": "intern",
            "briefDescription": "Source Documents: How the company handles invoices, receipts, and vouchers.\nJournalizing & Ledger Posting: Describe the software used (e.g., TallyPrime, SAP, QuickBooks, or MS Excel) for recording transactions.\nTrial Balance & Final Accounts: Your role in assisting with the preparation of Profit & Loss accounts or Balance Sheets. ",
            "keySkills": ""
          },
          "reportConfig": {
            "language": "English",
            "contentType": "Text, Image Of Data, Data Analysis And Interpretation",
            "policy": {
              "strictLanguageOnly": false,
              "allowedLanguages": [],
              "allowedScriptsRegex": "",
              "generationInstruction": "",
              "fallbackMessage": "",
              "uiLabels": {},
              "sectionTitleMap": {},
              "contentFeatures": [],
              "imagesRequired": false
            },
            "aiContext": "Commerce/Accounting internship report. Focus on: accounting principles, financial statements, auditing, taxation (GST, Income Tax), Tally/SAP, cost accounting, banking operations, budgeting, financial analysis. Include data analysis and interpretation.",
            "sections": [
              {
                "key": "acknowledgement",
                "title": "Acknowledgement",
                "description": "Thanks to mentors, college, company"
              },
              {
                "key": "abstract",
                "title": "Abstract",
                "description": "Brief 150-word summary of the entire report"
              },
              {
                "key": "introduction",
                "title": "Introduction",
                "description": "Internship objectives, scope, and overview"
              },
              {
                "key": "companyOverview",
                "title": "Company/Industry Overview",
                "description": "About the company, history, products, services"
              },
              {
                "key": "departmentStudy",
                "title": "Department/Division Study",
                "description": "Structure, functions of department worked in"
              },
              {
                "key": "workDescription",
                "title": "Work Description & Activities",
                "description": "Detailed daily/weekly work done during internship"
              },
              {
                "key": "learningOutcomes",
                "title": "Learning Outcomes",
                "description": "Skills, knowledge, competencies gained"
              },
              {
                "key": "challenges",
                "title": "Challenges & Solutions",
                "description": "Problems faced and how they were resolved"
              },
              {
                "key": "conclusion",
                "title": "Conclusion & Recommendations",
                "description": "Summary, future scope, suggestions"
              },
              {
                "key": "references",
                "title": "References",
                "description": "Books, websites, resources used"
              }
            ]
          }
        },
        "webhookUrl": "https://ai.ivinfotech.com/webhook/generate-report",
        "executionMode": "production"
      }
    ]
  },
  "meta": {
    "templateCredsSetupCompleted": true,
    "instanceId": "19b95c8862916f7a8961319d0510837acbdcda51734d2d435d4f1012841d27c0"
  }
}


// Split Into Sections

const body = $input.first().json.body;

if (!body) throw new Error('Request body is missing');
if (!body.student) throw new Error('Missing: body.student');
if (!body.college) throw new Error('Missing: body.college');
if (!body.university) throw new Error('Missing: body.university');
if (!body.reportConfig) throw new Error('Missing: body.reportConfig');
if (body.reportConfig.sections !== undefined && !Array.isArray(body.reportConfig.sections)) {
  throw new Error('reportConfig.sections must be an array if provided');
}

const student = body.student;
const college = body.college;
const university = body.university;
const industry = body.industry || {};
const internship = body.internship || {};
const config = body.reportConfig || {};
const policy = config.policy || {};

const reportId = body.reportId;
const callbackUrl = body.callbackUrl;

const rawLanguage = String(config.language || 'English').trim();
const dynamicInstruction = String(policy.generationInstruction || '').trim();
const strictLanguageOnly = policy.strictLanguageOnly === true;
const langKey = rawLanguage.toLowerCase().replace(/\s+/g, '_');

const langInstr = dynamicInstruction || [
  `Write in ${rawLanguage}.`,
  strictLanguageOnly
    ? 'Strict rule: Use only the target language/script. Do not mix other languages except unavoidable proper nouns.'
    : 'Keep language natural and professional for academic report writing.',
  'Do not use markdown formatting in output.',
].join(' ');

// ── Build format permission flags from config ──
const contentType = String(config.contentType || '').toLowerCase();
const genInstr = String(policy.generationInstruction || '').toLowerCase();
const allowTables   = (contentType.includes('table') || genInstr.includes('table'))   ? 'YES' : 'NO';
const allowBullets  = genInstr.includes('no bullet')   ? 'NO' : 'YES';
const allowSubtitles = genInstr.includes('no subtitle') ? 'NO' : 'YES';

// ── Auto-generate key from title if key is missing ──
const safeSections = (config.sections || [])
  .filter(s => s && s.title)
  .map(s => ({
    ...s,
    key: s.key || s.title.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '')
  }));

const defaultSections = [
  { key: 'acknowledgement',  title: 'Acknowledgement',             description: 'Thanks to mentors, institution, and supporters.' },
  { key: 'abstract',         title: 'Abstract',                    description: 'Summary of internship, activities, and outcomes.' },
  { key: 'introduction',     title: 'Introduction',                description: 'Background, objectives, and scope of internship.' },
  { key: 'workDescription',  title: 'Work Description & Activities', description: 'Detailed tasks, tools, process, and execution.' },
  { key: 'learningOutcomes', title: 'Learning Outcomes',           description: 'Skills, knowledge, and competencies gained.' },
  { key: 'conclusion',       title: 'Conclusion & Recommendations', description: 'Summary, reflections, and recommendations.' },
  { key: 'references',       title: 'References',                  description: 'Books, websites, papers, and other sources.' },
];

const sectionsToUse = safeSections.length ? safeSections : defaultSections;
if (!sectionsToUse.length) {
  throw new Error('No sections available. Please configure reportSections in the Major admin panel.');
}

const context = [
  `STUDENT: ${student.name} (Roll: ${student.rollNumber || 'N/A'}, Email: ${student.email || 'N/A'})`,
  `COLLEGE: ${college.name || 'N/A'}`,
  `UNIVERSITY: ${university.name || 'N/A'}`,
  `COMPANY: ${industry.name || 'N/A'}`,
  `PROJECT: ${internship.projectTitle || 'N/A'}`,
  `INTERNSHIP TITLE: ${internship.internshipTitle || 'N/A'}`,
  `DURATION: ${internship.duration || 'N/A'} (${internship.startDate || ''} to ${internship.endDate || ''})`,
  `SKILLS: ${internship.keySkills || 'N/A'}`,
  '',
  'WHAT STUDENT DID:',
  internship.briefDescription || '',
].join('\n');

const items = sectionsToUse.map((section, index) => {
  const isAbstract = section.key === 'abstract';

  const sectionSpecificPrompt = [
    `Write the "${section.title}" section.`,
    `Description: ${section.description || section.title}`,
    isAbstract
      ? 'Use THIRD PERSON for abstract. Write as flowing prose only. No bullets. No bold paragraphs.'
      : 'Use FIRST PERSON. Do not mention student by name. Use "I".',
    'Length: 280-420 words.',
  ].join('\n');

  const fullPrompt = [
    'You are writing ONE section of an academic internship report.',
    `The student ${student.name || 'Student'} is the author. Write AS the student unless section asks otherwise.`,
    '',
    langInstr,
    '',
    'CONTEXT:',
    context,
    '',
    '=== RETURN FORMAT (MUST BE VALID JSON) ===',
    'Return ONLY a JSON object with exactly these keys: sectionTitle, sectionContent, uiLabels, references',
    '- references: array of {title: string, url: string} for sources of any factual claims. Empty array if none.',
    '',
    '=== FORMATTING RULES ===',
    'Return sectionContent as plain text with optional structural tags only when truly needed.',
    '',
    'AVAILABLE TAGS:',
    '[TABLE_START]',
    'RealHeader1|RealHeader2|RealHeader3',
    'Value1|Value2|Value3',
    '[TABLE_END]',
    '',
    '[BULLET_START]',
    '- First point',
    '- Second point',
    '[BULLET_END]',
    '',
    '[SUBTITLE]Heading text here[/SUBTITLE]',
    '[SUBPOINT]Indented sub-paragraph here[/SUBPOINT]',
    '[BOLD]key phrase[/BOLD]',
    '',
    'STRICT RULES — NEVER VIOLATE:',
    '- The section heading is already printed by the PDF template. NEVER repeat the section title at the start of sectionContent.',
    '- NEVER open sectionContent with [SUBTITLE] that mirrors the section title.',
    '- [BOLD] applies only to 2–5 word key phrases. NEVER bold a full sentence or paragraph.',
    '- NEVER output placeholder column headers like Col1, Col2, Col3, HeaderA, HeaderB.',
    '- NEVER create a table unless you have REAL named columns with REAL comparable row data.',
    '- If tabular data does not exist, use [BULLET_START] list instead of a table.',
    '- Do NOT force bullets or subtitles into naturally flowing prose sections.',
    '- No markdown (no **, no #, no -).',
    '- Formulas may use LaTeX delimiters \\( \\) or \\[ \\].',
    `- Tables allowed: ${allowTables}. Bullets allowed: ${allowBullets}. Subtitles allowed: ${allowSubtitles}.`,
    'PLAGIARISM PREVENTION RULES (MANDATORY):',
    '- Do NOT copy-paste any text from the internet or known sources.',
    '- Paraphrase all facts, definitions, and concepts in your own words.',
    '- Do not include long quoted lines. If quoting is needed, keep it under 10 words and use quotation marks.',
    '- Add a references field in your JSON response: an array of objects with {title, url} for any factual claims.',
    '- Write originally. Similarity to existing web content must be below 5% per source.',
    '',
    '',
    '=== SECTION TO WRITE ===',
    `Section: "${section.title}"`,
    '',
    sectionSpecificPrompt,
  ].join('\n');

  return {
    json: {
      prompt: fullPrompt,
      sectionKey: section.key,
      sectionTitle: section.title,
      sectionIndex: index,
      totalSections: sectionsToUse.length,
      reportId,
      callbackUrl,
      configLanguage: rawLanguage,
      strictLanguageOnly,
      langKey,
    }
  };
});

return items;


// Merge All Sections

const allItems = $input.all();
const splitItems = $('Split Into Sections').all();

const generatedReferences = {};
const generatedContent = {};
const generatedTitles = {};
let generatedUiLabels = {};

const reportId = splitItems[0]?.json.reportId || '';
const callbackUrl = splitItems[0]?.json.callbackUrl || '';
const expectedCount = splitItems.length;

if (!reportId) throw new Error('Missing reportId from Split node');
if (!callbackUrl) throw new Error('Missing callbackUrl from Split node');

const firstMeta = splitItems[0]?.json || {};
const configLanguage = String(firstMeta.configLanguage || 'English');
const langKey = String(firstMeta.langKey || 'english');
const strictLanguageOnly = firstMeta.strictLanguageOnly === true;

const indexToKey = {};
const indexToTitle = {};
for (let i = 0; i < splitItems.length; i++) {
  indexToKey[i] = splitItems[i].json.sectionKey || '';
  indexToTitle[i] = splitItems[i].json.sectionTitle || '';
}

function stripCodeFences(text) {
  return String(text || '')
    .replace(/^```json\s*/i, '')
    .replace(/^```\s*/i, '')
    .replace(/```\s*$/i, '')
    .trim();
}

function extractJsonObjectText(text) {
  const t = String(text || '');
  const start = t.indexOf('{');
  const end = t.lastIndexOf('}');
  if (start === -1 || end === -1 || end <= start) return t;
  return t.slice(start, end + 1);
}

function parseSectionPayload(rawText) {
  const cleaned = stripCodeFences(rawText);
  const slice = extractJsonObjectText(cleaned);
  const candidates = [cleaned, slice];
  for (const c of candidates) {
    try {
      const obj = JSON.parse(c);
      if (obj && typeof obj === 'object') return obj;
    } catch (_) {}
  }
  throw new Error('Unable to parse AI JSON response');
}

function extractAiText(data) {
  if (Array.isArray(data.output)) {
    const firstMsg = data.output[0];
    if (firstMsg && Array.isArray(firstMsg.content)) {
      return firstMsg.content
        .filter(c => c && typeof c.text === 'string')
        .map(c => c.text)
        .join('\n')
        .trim();
    }
  }
  if (Array.isArray(data.content)) {
    return data.content
      .filter(c => c && typeof c.text === 'string')
      .map(c => c.text)
      .join('\n')
      .trim();
  }
  if (typeof data.output === 'string') return data.output;
  if (data.message?.content) return data.message.content;
  if (data.choices?.[0]?.message?.content) return data.choices[0].message.content;
  if (typeof data.text === 'string') return data.text;
  return '';
}

function hasInvalidScript(text) {
  if (!strictLanguageOnly || langKey === 'english') return false;
  let cleaned = String(text || '');
  cleaned = cleaned.replace(/\\\[[\s\S]*?\\\]/g, ' ');
  cleaned = cleaned.replace(/\\\([\s\S]*?\\\)/g, ' ');
  cleaned = cleaned.replace(/\\[A-Za-z]+/g, ' ');
  cleaned = cleaned.replace(/[{}_^]/g, ' ');
  const latinWords = cleaned.match(/\b[A-Za-z]{4,}\b/g) || [];
  return latinWords.length > 8;
}

for (let i = 0; i < allItems.length; i++) {
  const data = allItems[i].json;
  const sectionKey = indexToKey[i] || '';
  const sectionTitle = indexToTitle[i] || sectionKey;

  const aiJsonText = extractAiText(data);
  let parsed;
  try {
    parsed = parseSectionPayload(aiJsonText);
  } catch (e) {
    throw new Error(`Failed to parse section "${sectionTitle}": ${e.message}`);
  }

  const aiTitle = String(parsed.sectionTitle || '').trim() || sectionTitle;
  const aiContent = String(parsed.sectionContent || '').trim();
  const aiReferences = Array.isArray(parsed.references) ? parsed.references : [];
  const aiUiLabels = parsed.uiLabels && typeof parsed.uiLabels === 'object' ? parsed.uiLabels : null;

  if (!aiContent) throw new Error(`Empty content returned for section "${sectionTitle}"`);
  if (hasInvalidScript(aiContent)) {
    throw new Error(`Language policy violated in section "${sectionTitle}" for language "${configLanguage}"`);
  }

  if (sectionKey) {
    generatedContent[sectionKey] = aiContent;
    generatedReferences[sectionKey] = aiReferences;
    generatedTitles[sectionKey] = aiTitle;
    if (aiUiLabels && Object.keys(aiUiLabels).length > Object.keys(generatedUiLabels).length) {
      generatedUiLabels = aiUiLabels;
    }
  }
}

const actualCount = Object.keys(generatedContent).length;
if (actualCount < expectedCount) {
  throw new Error(`Incomplete: expected ${expectedCount} sections, got ${actualCount}`);
}

// ── Internal duplicate sentence check ──
const allSentences = [];
for (const key of Object.keys(generatedContent)) {
  const sentences = generatedContent[key]
    .split(/[.!?]+/)
    .map(s => s.trim().toLowerCase())
    .filter(s => s.length > 30);
  allSentences.push(...sentences.map(s => ({ sentence: s, key })));
}
const seen = {};
for (const { sentence, key } of allSentences) {
  if (seen[sentence]) {
    throw new Error(`Duplicate sentence detected across sections "${seen[sentence]}" and "${key}". Possible plagiarism risk.`);
  }
  seen[sentence] = key;
}

// ── Build ordered section list for backend TOC rendering ──
const orderedSections = Object.keys(indexToKey)
  .sort((a, b) => Number(a) - Number(b))
  .map(i => ({
    index: Number(i),
    key: indexToKey[i],
    title: generatedTitles[indexToKey[i]] || indexToTitle[i],
    content: generatedContent[indexToKey[i]] || '',
  }));

return [{
  json: {
    reportId,
    callbackUrl,
    generatedContent,
    generatedTitles,
    generatedUiLabels,
    generatedReferences,
    orderedSections,
    sectionCount: actualCount,
  }
}];
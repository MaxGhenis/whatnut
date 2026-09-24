// Quarto post-render script (paper/_quarto.yml, project: post-render): write
// target="_blank" and rel="noopener" into every external link of the rendered
// HTML, so each opens in a new tab.
//
// Why not Quarto's link-external-newwindow: Quarto applies that option from
// JavaScript in the page, and the wrapper at /whatnut/ frames the manuscript in
// an iframe sandboxed without allow-scripts. There, a DOI or GitHub link would
// navigate the frame itself to a site that refuses to be framed. Attributes in
// the HTML need no script, and allow-popups-to-escape-sandbox lets the new tab
// run normally.
//
// External means an href that starts with http:, https: or mailto:. The rewrite
// covers every <a> start tag outside <script>, <style>, <textarea>, <template>
// and comments: body links, the title block's author links and the
// bibliography's DOIs alike. It keeps an existing rel's tokens, sets any other
// target to _blank, and is idempotent.
//
// Quarto runs it with its bundled Deno after every project render, locally
// (paper/render_paper.py) and on Vercel (quarto only, no Python). It imports
// nothing, so it needs no network and no dependency. By hand:
//
//   quarto run paper/external_links.ts path/to/page.html [...]
//
// With no arguments it reads the rendered files from QUARTO_PROJECT_OUTPUT_FILES
// (or the file named by QUARTO_USE_FILE_FOR_PROJECT_OUTPUT_FILES), paths
// relative to the project directory, and skips everything but .html.

const EXTERNAL = /^\s*(?:https?:|mailto:)/i;

// An <a> start tag; attribute values may contain ">" inside quotes.
const A_TAG = /<(a)(?=[\s>])((?:[^>"']|"[^"]*"|'[^']*')*)>/gi;

// Regions whose text is not markup.
const OPAQUE =
  /<(script|style|textarea|template)\b(?:[^>"']|"[^"]*"|'[^']*')*>[\s\S]*?<\/\1\s*>|<!--[\s\S]*?-->/gi;

// One attribute: leading space, name, optional "= value".
const ATTR =
  /(\s+)([^\s"'>\/=]+)(?:(\s*=\s*)("[^"]*"|'[^']*'|[^\s"'>]+))?/g;

type Attr = {
  start: number;
  end: number;
  lead: string;
  name: string;
  value: string | null;
};

function parseAttrs(attrs: string): Attr[] {
  const out: Attr[] = [];
  for (const m of attrs.matchAll(ATTR)) {
    const raw = m[4];
    let value: string | null = null;
    if (raw !== undefined) {
      value = raw.startsWith('"') || raw.startsWith("'") ? raw.slice(1, -1) : raw;
    }
    out.push({
      start: m.index!,
      end: m.index! + m[0].length,
      lead: m[1],
      name: m[2].toLowerCase(),
      value,
    });
  }
  return out;
}

/** The attribute text of one <a> tag with the new-tab attributes, or the
 * input unchanged when the link is not external. */
export function fixAnchorAttrs(attrs: string): string {
  const parsed = parseAttrs(attrs);
  const href = parsed.find((a) => a.name === "href");
  if (!href || href.value === null || !EXTERNAL.test(href.value)) return attrs;

  const edits: { start: number; end: number; text: string }[] = [];
  const append: string[] = [];

  const target = parsed.find((a) => a.name === "target");
  if (!target) append.push(' target="_blank"');
  else if (target.value !== "_blank") {
    edits.push({ start: target.start, end: target.end, text: `${target.lead}target="_blank"` });
  }

  const rel = parsed.find((a) => a.name === "rel");
  if (!rel) append.push(' rel="noopener"');
  else {
    const tokens = (rel.value ?? "").split(/\s+/).filter(Boolean);
    if (!tokens.map((t) => t.toLowerCase()).includes("noopener")) {
      tokens.push("noopener");
      edits.push({ start: rel.start, end: rel.end, text: `${rel.lead}rel="${tokens.join(" ")}"` });
    }
  }

  let out = attrs;
  for (const e of edits.sort((a, b) => b.start - a.start)) {
    out = out.slice(0, e.start) + e.text + out.slice(e.end);
  }
  // Keep a trailing "/" (XHTML-style) last.
  const selfClose = /\s*\/\s*$/.exec(out);
  if (selfClose) {
    return out.slice(0, selfClose.index) + append.join("") + out.slice(selfClose.index);
  }
  return out + append.join("");
}

/** Rewrite every external link in an HTML document. */
export function openExternalLinksInNewTab(html: string): { html: string; external: number; changed: number } {
  let external = 0;
  let changed = 0;
  const fix = (segment: string) =>
    segment.replace(A_TAG, (whole, name: string, attrs: string) => {
      if (isExternal(attrs)) external++;
      const fixed = fixAnchorAttrs(attrs);
      if (fixed === attrs) return whole;
      changed++;
      return `<${name}${fixed}>`;
    });
  let out = "";
  let last = 0;
  for (const m of html.matchAll(OPAQUE)) {
    out += fix(html.slice(last, m.index!)) + m[0];
    last = m.index! + m[0].length;
  }
  out += fix(html.slice(last));
  return { html: out, external, changed };
}

function isExternal(attrs: string): boolean {
  const href = parseAttrs(attrs).find((a) => a.name === "href");
  return !!href && href.value !== null && EXTERNAL.test(href.value);
}

function renderedFiles(): string[] {
  if (Deno.args.length) return Deno.args;
  let list = Deno.env.get("QUARTO_PROJECT_OUTPUT_FILES");
  const listFile = Deno.env.get("QUARTO_USE_FILE_FOR_PROJECT_OUTPUT_FILES");
  if (list === undefined && listFile) list = Deno.readTextFileSync(listFile);
  if (list === undefined) {
    throw new Error(
      "external_links.ts: pass HTML files, or run as a Quarto post-render script",
    );
  }
  return list.split("\n").map((f) => f.trim()).filter(Boolean);
}

if (import.meta.main) {
  const quiet = Deno.env.get("QUARTO_PROJECT_SCRIPT_QUIET") === "1";
  for (const file of renderedFiles().filter((f) => /\.html?$/i.test(f))) {
    const before = Deno.readTextFileSync(file);
    const { html, external, changed } = openExternalLinksInNewTab(before);
    if (html !== before) Deno.writeTextFileSync(file, html);
    if (!quiet) {
      console.log(`external_links: ${file}: ${external} external links, ${changed} rewritten to open in a new tab`);
    }
  }
}

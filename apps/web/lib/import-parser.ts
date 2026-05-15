import type { AssetInput, ImportParseResult } from "@/types/analysis";

const REQUIRED_COLUMNS = ["ticker", "quantity", "average_price"];
const ACCEPTED_EXTENSIONS = ["csv", "pdf"] as const;
const MAX_IMPORT_SIZE_BYTES = 10 * 1024 * 1024;
const ACCEPTED_MIME_TYPES_BY_EXTENSION: Record<(typeof ACCEPTED_EXTENSIONS)[number], Set<string>> = {
  csv: new Set(["", "text/csv", "application/csv", "application/vnd.ms-excel"]),
  pdf: new Set(["", "application/pdf"]),
};
const REJECTED_FILE_SIGNATURES = ["%PDF-", "PK\x03\x04", "\x89PNG", "GIF8", "\xff\xd8\xff"];
const MESSAGES = {
  invalidFormat: "Formato invalido. Envie apenas arquivo CSV ou PDF.",
  emptyFile: "O arquivo esta vazio. Envie um CSV ou PDF com dados da carteira.",
  invalidFile: "Arquivo invalido ou corrompido. Verifique o arquivo e tente novamente.",
  invalidCsv: "CSV invalido. Use as colunas ticker, quantity e average_price.",
  invalidNumbers: "CSV invalido. Quantidade deve ser maior que zero e preco medio nao pode ser negativo.",
  fileTooLarge: "O arquivo excede o tamanho maximo permitido de 10 MB.",
  genericError: "Nao foi possivel importar o arquivo. Tente novamente ou preencha os ativos manualmente.",
} as const;

export async function parseBrokerageFile(file: File): Promise<ImportParseResult> {
  try {
    const extension = getFileExtension(file.name);
    if (!isAcceptedExtension(extension)) {
      return { ok: false, message: MESSAGES.invalidFormat };
    }

    if (!isAcceptedMimeType(extension, file.type)) {
      return { ok: false, message: MESSAGES.invalidFormat };
    }

    if (file.size === 0) {
      return { ok: false, message: MESSAGES.emptyFile };
    }

    if (file.size > MAX_IMPORT_SIZE_BYTES) {
      return { ok: false, message: MESSAGES.fileTooLarge };
    }

    if (extension === "pdf") {
      return parsePdfFile(file);
    }

    return parseCsvFile(file);
  } catch {
    return { ok: false, message: MESSAGES.genericError };
  }
}

function getFileExtension(fileName: string): string | null {
  const extension = fileName.split(".").pop()?.trim().toLowerCase();
  return extension && extension !== fileName.toLowerCase() ? extension : null;
}

function isAcceptedExtension(extension: string | null): extension is (typeof ACCEPTED_EXTENSIONS)[number] {
  return ACCEPTED_EXTENSIONS.some((acceptedExtension) => acceptedExtension === extension);
}

function isAcceptedMimeType(extension: (typeof ACCEPTED_EXTENSIONS)[number], mimeType: string) {
  return ACCEPTED_MIME_TYPES_BY_EXTENSION[extension].has(mimeType.toLowerCase());
}

async function parsePdfFile(file: File): Promise<ImportParseResult> {
  const signature = await file.slice(0, 5).text();
  if (signature !== "%PDF-") {
    return { ok: false, message: MESSAGES.invalidFile };
  }

  return {
    ok: false,
    message: "Nao foi possivel importar os ativos deste PDF. Envie um CSV com ticker, quantity e average_price.",
  };
}

async function parseCsvFile(file: File): Promise<ImportParseResult> {
  const text = await readTextFile(file);
  if (text === null) {
    return { ok: false, message: MESSAGES.invalidFile };
  }

  if (looksLikeCorruptedOrDisguisedCsv(text)) {
    return { ok: false, message: MESSAGES.invalidFile };
  }

  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length === 0) {
    return { ok: false, message: MESSAGES.emptyFile };
  }

  if (lines.length < 2) {
    return { ok: false, message: MESSAGES.invalidCsv };
  }

  const delimiter = lines[0].includes(";") ? ";" : ",";
  const headers = parseCsvLine(lines[0], delimiter).map((header) => header.trim().toLowerCase());
  const missingColumns = REQUIRED_COLUMNS.filter((column) => !headers.includes(column));

  if (missingColumns.length > 0) {
    return { ok: false, message: MESSAGES.invalidCsv };
  }

  const assets: AssetInput[] = [];
  for (const line of lines.slice(1)) {
    const values = parseCsvLine(line, delimiter).map((value) => value.trim());
    if (values.length !== headers.length) {
      return { ok: false, message: MESSAGES.invalidCsv };
    }

    const row = Object.fromEntries(headers.map((header, index) => [header, values[index]]));
    const ticker = String(row.ticker ?? "").trim().toUpperCase();
    const quantity = Number(row.quantity);
    const averagePrice = Number(row.average_price);

    if (!ticker || !Number.isFinite(quantity) || !Number.isFinite(averagePrice)) {
      return { ok: false, message: MESSAGES.invalidCsv };
    }

    if (quantity <= 0 || averagePrice < 0) {
      return { ok: false, message: MESSAGES.invalidNumbers };
    }

    assets.push({
      ticker,
      quantity,
      average_price: averagePrice,
      asset_type: String(row.asset_type ?? "stock"),
    });
  }

  return { ok: true, assets };
}

function looksLikeCorruptedOrDisguisedCsv(text: string) {
  const sample = text.slice(0, 64);
  if (REJECTED_FILE_SIGNATURES.some((signature) => sample.startsWith(signature))) {
    return true;
  }

  return sample.includes("\u0000");
}

async function readTextFile(file: File): Promise<string | null> {
  try {
    const buffer = await file.arrayBuffer();
    return new TextDecoder("utf-8", { fatal: true }).decode(buffer);
  } catch {
    return null;
  }
}

function parseCsvLine(line: string, delimiter: string): string[] {
  const values: string[] = [];
  let currentValue = "";
  let insideQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];
    const nextCharacter = line[index + 1];

    if (character === '"' && insideQuotes && nextCharacter === '"') {
      currentValue += character;
      index += 1;
      continue;
    }

    if (character === '"') {
      insideQuotes = !insideQuotes;
      continue;
    }

    if (character === delimiter && !insideQuotes) {
      values.push(currentValue);
      currentValue = "";
      continue;
    }

    currentValue += character;
  }

  if (insideQuotes) {
    return [];
  }

  values.push(currentValue);
  return values;
}

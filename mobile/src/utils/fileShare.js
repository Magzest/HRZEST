import { File, Paths } from "expo-file-system";
import * as Sharing from "expo-sharing";

// Shared by Analytics (plain CSV text) and Salary Report (base64 .xlsx
// bytes from the backend) export buttons -- both need the same
// write-to-cache-then-open-share-sheet flow, just with a different encoding.
async function _writeAndShare(filename, content, encoding, mimeType) {
  const file = new File(Paths.cache, filename);
  file.create({ overwrite: true });
  file.write(content, encoding ? { encoding } : undefined);

  try {
    if (await Sharing.isAvailableAsync()) {
      await Sharing.shareAsync(file.uri, { mimeType, dialogTitle: filename });
    }
    return file.uri;
  } finally {
    // These are financial documents (payslips, salary breakdowns) --
    // left unencrypted in the app's cache directory indefinitely
    // otherwise (this cache is never swept on its own). The share
    // intent has already handed the OS/receiving app the file by the
    // time shareAsync() resolves, so it's safe to remove here. Runs
    // even if sharing was unavailable or the user cancelled, so a
    // cancelled export doesn't leave a copy behind either. Best-effort:
    // a delete failure must not surface as an export failure to the user.
    try { file.delete(); } catch (_) {}
  }
}

export const shareTextFile = (filename, textContent, mimeType = "text/csv") =>
  _writeAndShare(filename, textContent, undefined, mimeType);

export const shareBase64File = (filename, base64Content, mimeType) =>
  _writeAndShare(filename, base64Content, "base64", mimeType);

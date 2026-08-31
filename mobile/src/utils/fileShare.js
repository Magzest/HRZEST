import { File, Paths } from "expo-file-system";
import * as Sharing from "expo-sharing";

// Shared by Analytics (plain CSV text) and Salary Report (base64 .xlsx
// bytes from the backend) export buttons -- both need the same
// write-to-cache-then-open-share-sheet flow, just with a different encoding.
async function _writeAndShare(filename, content, encoding, mimeType) {
  const file = new File(Paths.cache, filename);
  file.create({ overwrite: true });
  file.write(content, encoding ? { encoding } : undefined);

  if (await Sharing.isAvailableAsync()) {
    await Sharing.shareAsync(file.uri, { mimeType, dialogTitle: filename });
  }
  return file.uri;
}

export const shareTextFile = (filename, textContent, mimeType = "text/csv") =>
  _writeAndShare(filename, textContent, undefined, mimeType);

export const shareBase64File = (filename, base64Content, mimeType) =>
  _writeAndShare(filename, base64Content, "base64", mimeType);

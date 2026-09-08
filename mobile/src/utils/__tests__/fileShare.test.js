let mockFileInstance;

jest.mock('expo-file-system', () => {
  const instance = {
    create: jest.fn(),
    write: jest.fn(),
    uri: 'file:///mock-cache/mock-file',
  };
  return {
    __esModule: true,
    File: jest.fn().mockImplementation(() => instance),
    Paths: { cache: 'mock-cache-dir' },
    __mockFileInstance: instance,
  };
});

jest.mock('expo-sharing', () => ({
  __esModule: true,
  isAvailableAsync: jest.fn(),
  shareAsync: jest.fn(),
}));

const { File, Paths } = require('expo-file-system');
const Sharing = require('expo-sharing');
const { shareTextFile, shareBase64File } = require('../fileShare');

describe('fileShare', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFileInstance = require('expo-file-system').__mockFileInstance;
    Sharing.isAvailableAsync.mockResolvedValue(true);
  });

  describe('shareTextFile', () => {
    it('writes the file under the cache dir with no encoding option', async () => {
      await shareTextFile('report.csv', 'a,b,c');

      expect(File).toHaveBeenCalledWith(Paths.cache, 'report.csv');
      expect(mockFileInstance.create).toHaveBeenCalledWith({ overwrite: true });
      expect(mockFileInstance.write).toHaveBeenCalledWith('a,b,c', undefined);
    });

    it('defaults mimeType to text/csv and shares via the share sheet', async () => {
      await shareTextFile('report.csv', 'a,b,c');

      expect(Sharing.shareAsync).toHaveBeenCalledWith(mockFileInstance.uri, {
        mimeType: 'text/csv',
        dialogTitle: 'report.csv',
      });
    });

    it('honors an explicit mimeType', async () => {
      await shareTextFile('report.json', '{}', 'application/json');
      expect(Sharing.shareAsync).toHaveBeenCalledWith(mockFileInstance.uri, {
        mimeType: 'application/json',
        dialogTitle: 'report.json',
      });
    });

    it('resolves with the file uri', async () => {
      const uri = await shareTextFile('report.csv', 'a,b,c');
      expect(uri).toBe(mockFileInstance.uri);
    });

    it('skips opening the share sheet when sharing is unavailable, but still returns the uri', async () => {
      Sharing.isAvailableAsync.mockResolvedValue(false);
      const uri = await shareTextFile('report.csv', 'a,b,c');
      expect(Sharing.shareAsync).not.toHaveBeenCalled();
      expect(uri).toBe(mockFileInstance.uri);
    });
  });

  describe('shareBase64File', () => {
    it('writes the file with base64 encoding', async () => {
      await shareBase64File('salary.xlsx', 'QkFTRTY0', 'application/vnd.ms-excel');

      expect(File).toHaveBeenCalledWith(Paths.cache, 'salary.xlsx');
      expect(mockFileInstance.write).toHaveBeenCalledWith('QkFTRTY0', { encoding: 'base64' });
    });

    it('shares with the given mimeType and dialogTitle set to the filename', async () => {
      await shareBase64File('salary.xlsx', 'QkFTRTY0', 'application/vnd.ms-excel');
      expect(Sharing.shareAsync).toHaveBeenCalledWith(mockFileInstance.uri, {
        mimeType: 'application/vnd.ms-excel',
        dialogTitle: 'salary.xlsx',
      });
    });
  });
});

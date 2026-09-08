import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  saveLocalEmployee,
  deleteLocalEmployee,
  getLocalEmployees,
  mergeEmployeesWithLocal,
} from '../employeeStore';

const STORAGE_KEY = '@custom_created_employees_v1';

describe('employeeStore', () => {
  beforeEach(async () => {
    await AsyncStorage.clear();
  });

  describe('getLocalEmployees', () => {
    it('starts empty', async () => {
      expect(await getLocalEmployees()).toEqual([]);
    });

    it('returns [] if the stored value is corrupt JSON', async () => {
      await AsyncStorage.setItem(STORAGE_KEY, '{not json');
      expect(await getLocalEmployees()).toEqual([]);
    });
  });

  describe('saveLocalEmployee', () => {
    it('saves a new employee and prepends it (most-recent-first)', async () => {
      await saveLocalEmployee({ employee_id: 'E1', name: 'Alice' });
      const list = await saveLocalEmployee({ employee_id: 'E2', name: 'Bob' });
      expect(list.map((e) => e.employee_id)).toEqual(['E2', 'E1']);
    });

    it('replaces an existing employee with the same id rather than duplicating', async () => {
      await saveLocalEmployee({ employee_id: 'E1', name: 'Alice' });
      const list = await saveLocalEmployee({ employee_id: 'E1', name: 'Alice Updated' });
      expect(list).toHaveLength(1);
      expect(list[0].name).toBe('Alice Updated');
    });

    it('falls back to the "id" field when "employee_id" is absent', async () => {
      await saveLocalEmployee({ id: 'X1', name: 'Legacy' });
      const list = await saveLocalEmployee({ id: 'X1', name: 'Legacy Updated' });
      expect(list).toHaveLength(1);
      expect(list[0].name).toBe('Legacy Updated');
    });

    it('persists across calls via AsyncStorage', async () => {
      await saveLocalEmployee({ employee_id: 'E1', name: 'Alice' });
      const raw = await AsyncStorage.getItem(STORAGE_KEY);
      expect(JSON.parse(raw)).toEqual([{ employee_id: 'E1', name: 'Alice' }]);
    });
  });

  describe('deleteLocalEmployee', () => {
    it('removes only the matching employee', async () => {
      await saveLocalEmployee({ employee_id: 'E1', name: 'Alice' });
      await saveLocalEmployee({ employee_id: 'E2', name: 'Bob' });
      const list = await deleteLocalEmployee('E1');
      expect(list.map((e) => e.employee_id)).toEqual(['E2']);
    });

    it('is a no-op (returns unchanged list) when the id is not found', async () => {
      await saveLocalEmployee({ employee_id: 'E1', name: 'Alice' });
      const list = await deleteLocalEmployee('NOPE');
      expect(list).toHaveLength(1);
    });
  });

  describe('mergeEmployeesWithLocal', () => {
    it('returns just the local list when no server employees are given', async () => {
      await saveLocalEmployee({ employee_id: 'E1', name: 'Alice' });
      const merged = await mergeEmployeesWithLocal();
      expect(merged).toEqual([{ employee_id: 'E1', name: 'Alice' }]);
    });

    it('appends server employees that have no local counterpart', async () => {
      await saveLocalEmployee({ employee_id: 'E1', name: 'Alice (local)' });
      const merged = await mergeEmployeesWithLocal([{ employee_id: 'E2', name: 'Bob (server)' }]);
      expect(merged.map((e) => e.employee_id)).toEqual(['E1', 'E2']);
    });

    it('overlays server fields onto a matching local entry rather than duplicating it', async () => {
      await saveLocalEmployee({ employee_id: 'E1', name: 'Alice (local)', department: 'Eng' });
      const merged = await mergeEmployeesWithLocal([
        { employee_id: 'E1', name: 'Alice (server)' },
      ]);
      expect(merged).toHaveLength(1);
      // server fields win on conflict, but fields the server didn't send survive
      expect(merged[0]).toEqual({ employee_id: 'E1', name: 'Alice (server)', department: 'Eng' });
    });

    it('matches on the "id" field when "employee_id" is absent on either side', async () => {
      await saveLocalEmployee({ id: 'X1', name: 'Legacy local' });
      const merged = await mergeEmployeesWithLocal([{ id: 'X1', name: 'Legacy server' }]);
      expect(merged).toHaveLength(1);
      expect(merged[0].name).toBe('Legacy server');
    });

    it('degrades gracefully to the server list if reading local storage throws', async () => {
      // getLocalEmployees has its own internal try/catch (returns [] on
      // failure), so a storage read error surfaces here as "no local
      // employees" rather than as a thrown error -- confirm the merge
      // still produces the server list, not a crash.
      const spy = jest.spyOn(AsyncStorage, 'getItem').mockRejectedValueOnce(new Error('boom'));
      const serverEmployees = [{ employee_id: 'E9', name: 'Server Only' }];
      const merged = await mergeEmployeesWithLocal(serverEmployees);
      expect(merged).toEqual(serverEmployees);
      spy.mockRestore();
    });
  });
});

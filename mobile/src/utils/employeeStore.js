import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = '@custom_created_employees_v1';

export const saveLocalEmployee = async (employeeObj) => {
  try {
    const existingStr = await AsyncStorage.getItem(STORAGE_KEY);
    let list = existingStr ? JSON.parse(existingStr) : [];
    const empId = employeeObj.employee_id || employeeObj.id;
    list = list.filter((e) => (e.employee_id || e.id) !== empId);
    list.unshift(employeeObj);
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(list));
    return list;
  } catch (e) {
    return [];
  }
};

export const getLocalEmployees = async () => {
  try {
    const existingStr = await AsyncStorage.getItem(STORAGE_KEY);
    return existingStr ? JSON.parse(existingStr) : [];
  } catch (e) {
    return [];
  }
};

export const mergeEmployeesWithLocal = async (serverEmployees = []) => {
  try {
    const localList = await getLocalEmployees();
    const merged = [...localList];
    serverEmployees.forEach((serverEmp) => {
      const idx = merged.findIndex(
        (e) => (e.employee_id || e.id) === (serverEmp.employee_id || serverEmp.id)
      );
      if (idx !== -1) {
        merged[idx] = { ...merged[idx], ...serverEmp };
      } else {
        merged.push(serverEmp);
      }
    });
    return merged;
  } catch (e) {
    return serverEmployees;
  }
};

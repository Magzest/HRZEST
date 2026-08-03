import React from "react";
import { View, StyleSheet } from "react-native";
import SalaryEmployeeCard from "./SalaryEmployeeCard";
import EmptySalaryState from "./EmptySalaryState";

export default function EmployeeSalaryList({ employees = [], onSelectEmployee }) {
  if (!employees || employees.length === 0) {
    return <EmptySalaryState title="No Employee Records" subtitle="No salary records match your search." />;
  }

  return (
    <View style={styles.container}>
      {employees.map((employee, index) => (
        <SalaryEmployeeCard
          key={employee.id || employee.employeeId || index}
          employee={employee}
          onView={() => onSelectEmployee && onSelectEmployee(employee)}
          onDownload={() => onSelectEmployee && onSelectEmployee(employee)}
          onEmail={() => onSelectEmployee && onSelectEmployee(employee)}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginTop: 12,
    marginBottom: 20,
  },
});

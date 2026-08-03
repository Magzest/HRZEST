import React, { useState, useEffect } from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Alert,
  Modal,
  View,
  Text,
  TouchableOpacity,
  FlatList,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import AdminHeader from "../../components/admin/AdminHeader";
import SalaryHeader from "../../components/admin/salary/SalaryHeader";
import SalarySearchBar from "../../components/admin/salary/SalarySearchBar";
import MonthYearSelector from "../../components/admin/salary/MonthYearSelector";
import PayrollSummaryCard from "../../components/admin/salary/PayrollSummaryCard";
import SalaryStatsGrid from "../../components/admin/salary/SalaryStatsGrid";
import PayrollActionButtons from "../../components/admin/salary/PayrollActionButtons";
import EmployeeSalaryList from "../../components/admin/salary/EmployeeSalaryList";
import SALARY_THEME from "../../constants/salaryTheme";
import { fetchSalaryReport } from "../../api/client";
import SaasFilterSheet from "../../components/common/SaasFilterSheet";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

const YEARS = ["2024", "2025", "2026", "2027"];

export default function SalaryPayslipsScreen({ navigation }) {
  const [search, setSearch] = useState("");
  const [selectedMonth, setSelectedMonth] = useState("July");
  const [selectedYear, setSelectedYear] = useState("2026");
  const [selectedStatus, setSelectedStatus] = useState("All");
  const [selectedDept, setSelectedDept] = useState("All");
  const [selectedSort, setSelectedSort] = useState("Highest Net Pay");
  const [filterModalVisible, setFilterModalVisible] = useState(false);

  const [monthModalVisible, setMonthModalVisible] = useState(false);
  const [yearModalVisible, setYearModalVisible] = useState(false);

  const [salaryOverview, setSalaryOverview] = useState({
    totalEmployees: 0,
    totalGross: 0,
    totalNetPay: 0,
    totalDeductions: 0,
    payrollStatus: "Draft",
  });

  const [employees, setEmployees] = useState([]);

  useEffect(() => {
    loadSalaryData();
  }, [selectedMonth, selectedYear]);

  const loadSalaryData = async () => {
    try {
      const monthIdx = MONTHS.indexOf(selectedMonth) + 1;
      const res = await fetchSalaryReport(selectedYear, monthIdx);
      if (res?.data) {
        if (res.data.overview) setSalaryOverview(res.data.overview);
        if (Array.isArray(res.data.employees)) setEmployees(res.data.employees);
      }
    } catch (_) {}
  };

  const handleGeneratePayroll = () => {
    Alert.alert(
      "Generate Payroll",
      `Generating payroll report for ${selectedMonth} ${selectedYear}...`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Confirm",
          onPress: () => {
            setSalaryOverview((prev) => ({
              ...prev,
              payrollStatus: "Completed",
            }));
            Alert.alert(
              "Success",
              `Payroll report for ${selectedMonth} ${selectedYear} generated successfully.`
            );
          },
        },
      ]
    );
  };

  const hasActiveFilter = selectedStatus !== "All" || selectedDept !== "All" || selectedSort !== "Highest Net Pay";

  const departments = ["All", "Engineering", "Human Resources", "Design", "Quality Assurance"];
  const statuses = ["All", "Paid", "Pending"];
  const sortOptions = ["Highest Net Pay", "Lowest Net Pay", "Name (A-Z)"];

  const filteredEmployees = employees
    .filter((e) => {
      const matchesSearch =
        e.name.toLowerCase().includes(search.toLowerCase()) ||
        e.role.toLowerCase().includes(search.toLowerCase()) ||
        (e.employeeId && e.employeeId.toLowerCase().includes(search.toLowerCase()));

      const matchesStatus =
        selectedStatus === "All" ||
        e.status === selectedStatus ||
        e.payrollStatus === selectedStatus;

      const matchesDept =
        selectedDept === "All" || e.department === selectedDept;

      return matchesSearch && matchesStatus && matchesDept;
    })
    .sort((a, b) => {
      const netA = a.netSalary ?? a.net ?? 0;
      const netB = b.netSalary ?? b.net ?? 0;
      if (selectedSort === "Lowest Net Pay") return netA - netB;
      if (selectedSort === "Name (A-Z)") return a.name.localeCompare(b.name);
      return netB - netA;
    });

  return (
    <SafeAreaView style={styles.container}>
      <AdminHeader title="Salary & Payslips" navigation={navigation} />

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <SalaryHeader
          month={selectedMonth}
          year={selectedYear}
          onSettingsPress={() => navigation.navigate("Settings")}
        />

        <SalarySearchBar
          value={search}
          onChangeText={setSearch}
          onClear={() => setSearch("")}
          onFilterPress={() => setFilterModalVisible(true)}
          hasActiveFilter={hasActiveFilter}
        />

        <MonthYearSelector
          selectedMonth={selectedMonth}
          selectedYear={selectedYear}
          onMonthPress={() => setMonthModalVisible(true)}
          onYearPress={() => setYearModalVisible(true)}
          onGeneratePress={handleGeneratePayroll}
        />

        <PayrollSummaryCard
          month={selectedMonth}
          year={selectedYear}
          totalEmployees={salaryOverview.totalEmployees}
          totalGross={salaryOverview.totalGross}
          totalNet={salaryOverview.totalNetPay}
          totalDeductions={salaryOverview.totalDeductions}
          payrollStatus={salaryOverview.payrollStatus}
          onGeneratePayroll={handleGeneratePayroll}
        />

        <SalaryStatsGrid
          totalEmployees={salaryOverview.totalEmployees}
          grossSalary={salaryOverview.totalGross}
          deductions={salaryOverview.totalDeductions}
          netSalary={salaryOverview.totalNetPay}
        />

        <PayrollActionButtons
          onGenerate={handleGeneratePayroll}
          onExport={() => Alert.alert("Export", "Exporting salary CSV summary...")}
          onEmail={() => Alert.alert("Email Sent", "Bulk payslip emails dispatched to staff.")}
          onMore={() => Alert.alert("Options", "Additional payroll rules available under Settings.")}
        />

        <EmployeeSalaryList
          employees={filteredEmployees}
          onSelectEmployee={(emp) =>
            Alert.alert("Employee Payslip", `${emp.name} (${emp.role})\nNet Pay: ₹${emp.net.toLocaleString()}\nStatus: ${emp.status}`)
          }
        />
      </ScrollView>

      {/* Month Selector Modal */}
      <Modal
        visible={monthModalVisible}
        transparent={true}
        animationType="fade"
        onRequestClose={() => setMonthModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Select Month</Text>
              <TouchableOpacity onPress={() => setMonthModalVisible(false)}>
                <Ionicons name="close" size={22} color="#0F172A" />
              </TouchableOpacity>
            </View>
            <FlatList
              data={MONTHS}
              keyExtractor={(item) => item}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[
                    styles.pickerOption,
                    selectedMonth === item && styles.pickerOptionActive,
                  ]}
                  onPress={() => {
                    setSelectedMonth(item);
                    setMonthModalVisible(false);
                  }}
                >
                  <Text
                    style={[
                      styles.pickerOptionText,
                      selectedMonth === item && styles.pickerOptionTextActive,
                    ]}
                  >
                    {item}
                  </Text>
                  {selectedMonth === item && (
                    <Ionicons name="checkmark-circle" size={18} color="#0B2253" />
                  )}
                </TouchableOpacity>
              )}
            />
          </View>
        </View>
      </Modal>

      {/* Year Selector Modal */}
      <Modal
        visible={yearModalVisible}
        transparent={true}
        animationType="fade"
        onRequestClose={() => setYearModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Select Year</Text>
              <TouchableOpacity onPress={() => setYearModalVisible(false)}>
                <Ionicons name="close" size={22} color="#0F172A" />
              </TouchableOpacity>
            </View>
            <FlatList
              data={YEARS}
              keyExtractor={(item) => item}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[
                    styles.pickerOption,
                    selectedYear === item && styles.pickerOptionActive,
                  ]}
                  onPress={() => {
                    setSelectedYear(item);
                    setYearModalVisible(false);
                  }}
                >
                  <Text
                    style={[
                      styles.pickerOptionText,
                      selectedYear === item && styles.pickerOptionTextActive,
                    ]}
                  >
                    {item}
                  </Text>
                  {selectedYear === item && (
                    <Ionicons name="checkmark-circle" size={18} color="#0B2253" />
                  )}
                </TouchableOpacity>
              )}
            />
          </View>
        </View>
      </Modal>

        {/* Professional SaaS Filter Modal */}
        <SaasFilterSheet
          visible={filterModalVisible}
          title="Filter Salary & Payroll"
          statusOptions={statuses}
          selectedStatus={selectedStatus}
          onSelectStatus={setSelectedStatus}
          deptOptions={departments}
          selectedDept={selectedDept}
          onSelectDept={setSelectedDept}
          sortOptions={sortOptions}
          selectedSort={selectedSort}
          onSelectSort={setSelectedSort}
          onApply={() => setFilterModalVisible(false)}
          onReset={() => {
            setSelectedStatus("All");
            setSelectedDept("All");
            setSelectedSort("Highest Net Pay");
          }}
          onClose={() => setFilterModalVisible(false)}
        />
      </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: SALARY_THEME.colors.background,
  },
  scrollView: {
    flex: 1,
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 110,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.5)",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 24,
  },
  modalCard: {
    width: "100%",
    maxHeight: 380,
    backgroundColor: "#FFFFFF",
    borderRadius: 22,
    padding: 20,
    elevation: 10,
    shadowColor: "#0F172A",
    shadowOpacity: 0.2,
    shadowRadius: 16,
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 14,
    paddingBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: "#E2E8F0",
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: "#0F172A",
  },
  pickerOption: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: 12,
    borderRadius: 12,
    marginBottom: 4,
  },
  pickerOptionActive: {
    backgroundColor: "#EFF6FF",
  },
  pickerOptionText: {
    fontSize: 15,
    fontWeight: "600",
    color: "#334155",
  },
  pickerOptionTextActive: {
    fontWeight: "800",
    color: "#0B2253",
  },
});
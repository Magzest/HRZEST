import React, {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  View,
} from "react-native";

import AdminHeader from "../../components/admin/AdminHeader";

import CompOffHeaderCard from "../../components/admin/CompOffHeaderCard";
import CompOffSummaryCard from "../../components/admin/CompOffSummaryCard";
import CompOffStatsGrid from "../../components/admin/CompOffStatsGrid";
import MonthYearSelector from "../../components/admin/MonthYearSelector";
import CompOffSegmentTabs from "../../components/admin/CompOffSegmentTabs";
import OvertimeHistoryCard from "../../components/admin/OvertimeHistoryCard";
import CompOffBalanceCard from "../../components/admin/CompOffBalanceCard";
import CompOffApplicationCard from "../../components/admin/CompOffApplicationCard";
import CompOffQuickActions from "../../components/admin/CompOffQuickActions";
import CompOffAnalyticsCard from "../../components/admin/CompOffAnalyticsCard";
import CompOffInfoCard from "../../components/admin/CompOffInfoCard";
import CompOffFilterSheet from "../../components/admin/CompOffFilterSheet";
import CompOffBottomSheet from "../../components/admin/CompOffBottomSheet";
import CompOffEmptyState from "../../components/admin/CompOffEmptyState";

import COMPOFF_THEME from "../../constants/compOffTheme";
import { fetchOvertime, fetchCompOff } from "../../api/client";

export default function CompOffScreen({
  navigation,
}) {
  const [selectedMonth, setSelectedMonth] = useState("August");
  const [selectedYear, setSelectedYear] = useState("2026");
  const [selectedTab, setSelectedTab] = useState("overtime");
  const [filterVisible, setFilterVisible] = useState(false);
  const [selectedStatus, setSelectedStatus] = useState("All");
  const [selectedDepartment, setSelectedDepartment] = useState("All");
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [detailsVisible, setDetailsVisible] = useState(false);

  const [overtimeData, setOvertimeData] = useState([]);
  const [balancesData, setBalancesData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    try {
      const [otRes, compRes] = await Promise.all([
        fetchOvertime().catch(() => null),
        fetchCompOff().catch(() => null),
      ]);
      if (otRes?.data?.ok && Array.isArray(otRes.data.overtime)) {
        setOvertimeData(otRes.data.overtime);
      } else {
        setOvertimeData([]);
      }
      if (compRes?.data?.ok && Array.isArray(compRes.data.balances)) {
        setBalancesData(compRes.data.balances);
      } else {
        setBalancesData([]);
      }
    } catch {
      setOvertimeData([]);
      setBalancesData([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const compOffSummary = useMemo(() => {
    const totalOtHours = overtimeData.reduce((acc, curr) => acc + Number(curr.hours || curr.ot_hours || 0), 0);
    const approvedRequests = overtimeData.filter((item) => item.status === "Approved").length;
    const pendingApproval = overtimeData.filter((item) => item.status === "Pending").length;
    const rejectedRequests = overtimeData.filter((item) => item.status === "Rejected").length;
    const compOffAvailable = balancesData.reduce((acc, curr) => acc + Number(curr.balance || 0), 0);
    const otPay = totalOtHours * 250;
    return {
      totalOtHours,
      approvedRequests,
      pendingApproval,
      rejectedRequests,
      compOffAvailable,
      otPay: "₹" + otPay.toLocaleString("en-IN"),
    };
  }, [overtimeData, balancesData]);

  const analytics = useMemo(() => {
    const totalRecords = overtimeData.length;
    const averageHours = totalRecords > 0 ? (compOffSummary.totalOtHours / totalRecords).toFixed(1) : "0.0";
    return { averageHours };
  }, [overtimeData, compOffSummary]);

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const filteredHistory = useMemo(() => {
    return overtimeData.filter((item) => {
      const statusMatch =
        selectedStatus === "All" ||
        item.status === selectedStatus;
      const departmentMatch =
        selectedDepartment === "All" ||
        item.department === selectedDepartment;
      return statusMatch && departmentMatch;
    });
  }, [overtimeData, selectedStatus, selectedDepartment]);

  const openRecord = (item) => {
    setSelectedRecord(item);
    setDetailsVisible(true);
  };

  return (

    <SafeAreaView style={styles.container}>

      <AdminHeader
        title="OT & Comp-off"
        onMenu={() =>
          navigation.openDrawer()
        }
      />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={
          styles.content
        }
      >

        <CompOffHeaderCard
          month={selectedMonth}
          year={selectedYear}
          totalHours={
            compOffSummary.totalOtHours
          }
          availableCompOff={
            compOffSummary.compOffAvailable
          }
          onSettings={() => {}}
        />

        <CompOffSummaryCard
          totalHours={
            compOffSummary.totalOtHours
          }
          otPay={compOffSummary.otPay}
          pendingApproval={
            compOffSummary.pendingApproval
          }
          availableCompOff={
            compOffSummary.compOffAvailable
          }
        />

        <CompOffStatsGrid
          approvedRequests={
            compOffSummary.approvedRequests
          }
          pendingRequests={
            compOffSummary.pendingApproval
          }
          rejectedRequests={
            compOffSummary.rejectedRequests
          }
          averageHours={
            analytics.averageHours
          }
        />
                <CompOffQuickActions
          onApplyOT={() => {}}
          onRequestCompOff={() => {}}
          onHistory={() =>
            setSelectedTab("overtime")
          }
          onExport={() => {}}
        />

        <CompOffSegmentTabs
          selectedTab={selectedTab}
          onChangeTab={setSelectedTab}
        />

        <MonthYearSelector
          month={selectedMonth}
          year={selectedYear}
          months={monthOptions}
          years={yearOptions}
          onMonthChange={setSelectedMonth}
          onYearChange={setSelectedYear}
          onFilterPress={() =>
            setFilterVisible(true)
          }
        />

        {/* ==========================
            OVERTIME TAB
        ========================== */}

        {selectedTab === "overtime" && (

          filteredHistory.length > 0 ? (

            filteredHistory.map((item) => (

              <OvertimeHistoryCard
                key={item.id}
                item={item}
                onPress={openRecord}
              />

            ))

          ) : (

            <CompOffEmptyState
              title="No Overtime Records"
              description="There are no overtime entries available for the selected filters."
              buttonTitle="Clear Filters"
              onPress={() => {
                setSelectedStatus("All");
                setSelectedDepartment("All");
              }}
            />

          )

        )}

        {/* ==========================
            COMP-OFF TAB
        ========================== */}

        {selectedTab === "compoff" && (

          <>

            {compOffBalances.map((balance) => (

              <CompOffBalanceCard
                key={balance.id}
                availableDays={
                  balance.availableDays
                }
                usedDays={
                  balance.usedDays
                }
                remainingDays={
                  balance.remainingDays
                }
                expiryDate={
                  balance.expiryDate
                }
              />

            ))}

            {filteredHistory
              .filter(
                (item) =>
                  item.compOffEarned > 0
              )
              .map((item) => (

                <CompOffApplicationCard
                  key={`co-${item.id}`}
                  item={{
                    employeeName:
                      item.employeeName,

                    department:
                      item.department,

                    startDate:
                      item.date,

                    endDate:
                      item.date,

                    days:
                      item.compOffEarned,

                    reason:
                      item.reason,

                    status:
                      item.status,
                  }}
                  onPress={() => {}}
                />

              ))}

            <CompOffInfoCard
              policies={compOffPolicies}
            />

          </>

        )}
                {/* ==========================
            ANALYTICS TAB
        ========================== */}

        {selectedTab === "analytics" && (

          <>

            <CompOffAnalyticsCard
              weeklyHours={analytics.weeklyHours}
              monthlyHours={analytics.monthlyHours}
              averageHours={analytics.averageHours}
              approvalRate={analytics.approvalRate}
            />

            <CompOffInfoCard
              policies={compOffPolicies}
            />

          </>

        )}

      </ScrollView>

      {/* ==========================
          FILTER SHEET
      ========================== */}

      <CompOffFilterSheet
        visible={filterVisible}
        selectedStatus={selectedStatus}
        selectedDepartment={selectedDepartment}
        onSelectStatus={setSelectedStatus}
        onSelectDepartment={
          setSelectedDepartment
        }
        onApply={() =>
          setFilterVisible(false)
        }
        onReset={() => {
          setSelectedStatus("All");
          setSelectedDepartment("All");
        }}
        onClose={() =>
          setFilterVisible(false)
        }
      />

      {/* ==========================
          DETAILS SHEET
      ========================== */}

      <CompOffBottomSheet
        visible={detailsVisible}
        record={selectedRecord}
        onClose={() => {
          setDetailsVisible(false);
          setSelectedRecord(null);
        }}
      />

    </SafeAreaView>

  );

}

const styles = StyleSheet.create({

  container: {

    flex: 1,

    backgroundColor:
      COMPOFF_THEME.colors.background,
  },

  content: {

    paddingHorizontal: 18,

    paddingTop: 12,

    paddingBottom: 120,
  },

});
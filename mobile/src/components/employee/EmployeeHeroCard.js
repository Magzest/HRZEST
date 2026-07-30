import React from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";
import { useNavigation, DrawerActions } from "@react-navigation/native";

export default function EmployeeHeroCard({
  employeeName,
  designation,
  employeeId,
  date,
  attendance,
  onCheckIn,
  checking,
  onMenu,
  onLogout,
  photoUrl,
  onScanQR,
  companyName,
}) {
  const navigation = useNavigation();

  const handleMenu = () => {
    if (typeof onMenu === "function") {
      try {
        onMenu();
      } catch (e) {
        navigation.dispatch(DrawerActions.openDrawer());
      }
    } else {
      navigation.dispatch(DrawerActions.openDrawer());
    }
  };

  const checkedIn =
    attendance?.login_time &&
    !attendance?.logout_time;

  const completed =
    attendance?.login_time &&
    attendance?.logout_time;

  const checkIn =
    attendance?.login_time
      ? attendance.login_time.slice(0,5)
      : "--:--";

  const checkOut =
    attendance?.logout_time
      ? attendance.logout_time.slice(0,5)
      : "--:--";

  const workedHours =
    attendance?.working_hours ||
    attendance?.hours ||
    "0h 00m";

  const greeting = () => {

    const hour = new Date().getHours();

    if(hour < 12) return "Good Morning";

    if(hour < 17) return "Good Afternoon";

    return "Good Evening";

  };

  const status = completed
    ? "Completed"
    : checkedIn
    ? "Working"
    : "Not Checked In";

  return (

    <View style={styles.card}>

      {/* Top Row */}

      <View style={styles.topRow}>
        <TouchableOpacity
          onPress={handleMenu}
          activeOpacity={0.7}
          style={styles.menuButton}
        >
          <Ionicons
            name="menu-sharp"
            size={22}
            color="#0F172A"
          />
        </TouchableOpacity>

        <View style={styles.headerTitleGroup}>
          <View style={styles.headerTag}>
            <Text style={styles.headerTagText}>EMPLOYEE PORTAL</Text>
          </View>
          <Text style={styles.headerBrandTitle}>Dashboard</Text>
        </View>

        <TouchableOpacity
          style={styles.iconBtn}
          onPress={onLogout}
          activeOpacity={0.7}
        >
          <Ionicons
            name="log-out-outline"
            size={20}
            color="#0F172A"
          />
        </TouchableOpacity>
      </View>

      {/* User */}

      <View style={styles.userRow}>

        <View style={styles.avatar}>

          <Ionicons
            name="person"
            size={32}
            color="#173B8C"
          />

          <View style={styles.onlineDot}/>

        </View>

        <View style={{flex:1}}>

          <Text style={styles.greeting}>
            {greeting()}
          </Text>

          <Text style={styles.name}>
            {employeeName || "Employee"}
          </Text>

          <Text style={styles.designation}>
            {designation || "🟦 Software Engineer"}
          </Text>

          {!!companyName && (
            <View style={styles.companyBadge}>
              <Ionicons name="business-outline" size={11} color="#1d4ed8" />
              <Text style={styles.companyText}>{companyName}</Text>
            </View>
          )}

        </View>

      </View>

      {/* Divider */}

      <View style={styles.divider}/>

      {/* Info */}

      


      {/* Button */}

      
    </View>

  );

}

const styles = StyleSheet.create({

  card:{
    backgroundColor:"#FFFFFF",
    borderRadius:24,
    padding:20,
    marginBottom:20,
    shadowColor:"#000",
    shadowOpacity:0.08,
    shadowRadius:14,
    shadowOffset:{width:0,height:8},
    elevation:5,
  },
  statusCard: {
  marginTop: 6,
  backgroundColor: "#F8FAFC",
  borderRadius: 18,
  padding: 18,
  flexDirection: "row",
  justifyContent: "space-between",
  alignItems: "center",
},

statusLeft: {
  flexDirection: "row",
  alignItems: "center",
},

statusIndicator: {
  width: 12,
  height: 12,
  borderRadius: 6,
  marginRight: 12,
},

hoursBadge: {
  backgroundColor: "#EEF4FF",
  borderRadius: 14,
  paddingHorizontal: 16,
  paddingVertical: 10,
  alignItems: "center",
},

hoursValue: {
  fontSize: 18,
  fontWeight: "800",
  color: "#173B8C",
},

hoursLabel: {
  marginTop: 2,
  fontSize: 11,
  color: "#64748B",
},

  topRow: {
  flexDirection: "row",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: 22,
},
iconBtn: {
  width: 46,
  height: 46,
  borderRadius: 16,
  backgroundColor: "#FFFFFF",

  justifyContent: "center",
  alignItems: "center",

  shadowColor: "#000",
  shadowOpacity: 0.08,
  shadowRadius: 12,
  shadowOffset: {
    width: 0,
    height: 5,
  },
  elevation: 5,
},

  iconBtn:{
    width:42,
    height:42,
    borderRadius:14,
    backgroundColor:"#F3F7FD",
    justifyContent:"center",
    alignItems:"center",
  },

  userRow:{
    flexDirection:"row",
    alignItems:"center",
  },

  avatar:{
    width:72,
    height:72,
    borderRadius:36,
    backgroundColor:"#EEF4FF",
    justifyContent:"center",
    alignItems:"center",
    marginRight:16,
    position:"relative",
  },

  onlineDot:{
    position:"absolute",
    bottom:5,
    right:6,
    width:14,
    height:14,
    borderRadius:7,
    backgroundColor:"#22C55E",
    borderWidth:2,
    borderColor:"#FFF",
  },

  greeting:{
    color:"#64748B",
    fontSize:13,
    fontWeight:"600",
  },

  name:{
    fontSize:22,
    fontWeight:"800",
    color:"#0F172A",
    marginTop:3,
  },

  designation:{
    marginTop:4,
    color:"#64748B",
    fontSize:15,
  },

  companyBadge:{
    flexDirection:"row",
    alignItems:"center",
    marginTop:6,
    backgroundColor:"#eff6ff",
    alignSelf:"flex-start",
    paddingHorizontal:8,
    paddingVertical:3,
    borderRadius:10,
    gap:4,
  },

  companyText:{
    color:"#1d4ed8",
    fontSize:11,
    fontWeight:"700",
  },

  divider:{
    height:1,
    backgroundColor:"#EEF2F7",
    marginVertical:18,
  },

  infoRow:{
    flexDirection:"row",
    justifyContent:"space-between",
    alignItems:"center",
    marginBottom:18,
  },

  badge:{
    flexDirection:"row",
    alignItems:"center",
    backgroundColor:"#EEF4FF",
    paddingHorizontal:12,
    paddingVertical:8,
    borderRadius:20,
  },

  badgeText:{
    marginLeft:6,
    color:"#173B8C",
    fontWeight:"700",
    fontSize:13,
  },

  dateRow:{
    flexDirection:"row",
    alignItems:"center",
  },

  date:{
    marginLeft:5,
    color:"#64748B",
    fontSize:13,
  },

  attendanceCard:{
    backgroundColor:"#F8FAFC",
    borderRadius:18,
    padding:18,
  },

  attRow:{
    flexDirection:"row",
    justifyContent:"space-between",
  },

  attBox:{
    flex:1,
    alignItems:"center",
  },

  attLabel:{
    color:"#64748B",
    marginTop:6,
    fontSize:13,
  },

  attTime:{
    marginTop:6,
    fontSize:24,
    fontWeight:"800",
    color:"#0F172A",
  },

  bottomRow:{
    flexDirection:"row",
    justifyContent:"space-between",
    marginTop:20,
    paddingTop:18,
    borderTopWidth:1,
    borderColor:"#E5E7EB",
  },

  smallTitle:{
    color:"#94A3B8",
    fontSize:12,
  },

  status:{
    marginTop:4,
    fontSize:16,
    fontWeight:"700",
    color:"#0F172A",
  },

  button:{
    marginTop:20,
    height:56,
    borderRadius:18,
    backgroundColor:"#173B8C",
    flexDirection:"row",
    justifyContent:"center",
    alignItems:"center",
  },

  checkout:{
    backgroundColor:"#EF4444",
  },

  buttonText:{
    color:"#FFF",
    fontWeight:"700",
    fontSize:16,
    marginLeft:8,
  },
  menuButton: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: "#F8FAFC",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  iconBtn: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: "#F8FAFC",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  headerTitleGroup: {
    flex: 1,
    marginLeft: 12,
    marginRight: 8,
    justifyContent: "center",
  },
  headerTag: {
    alignSelf: "flex-start",
    backgroundColor: "#EEF4FF",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    marginBottom: 2,
  },
  headerTagText: {
    fontSize: 9,
    fontWeight: "800",
    color: "#173B8C",
    letterSpacing: 0.6,
  },
  headerBrandTitle: {
    fontSize: 19,
    fontWeight: "700",
    color: "#0F172A",
    letterSpacing: -0.4,
  },
});
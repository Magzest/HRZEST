import React from 'react';
import {
  View,
  Text,
  StyleSheet,
} from 'react-native';

import { Ionicons } from '@expo/vector-icons';

import AppCard from '../ui/AppCard';
import SectionHeader from '../ui/SectionHeader';
import EmptyState from '../ui/EmptyState';
import Avatar from '../ui/Avatar';
import StatusChip from '../ui/StatusChip';
import Divider from '../ui/Divider';

export default function AttendanceCard({ rows = [] }) {

  return (

    <View style={styles.container}>

      <SectionHeader
        title="Today's Attendance"
        subtitle={`${rows.length} employee${rows.length === 1 ? "" : "s"} recorded`}
      />

      <AppCard style={styles.card}>

        {

          rows.length === 0 ? (

            <EmptyState
              icon="people-outline"
              title="No Attendance"
              subtitle="No employees have checked in today."
            />

          ) : (

            rows.map((employee, index) => {

              const status =
                employee.attendance_type ||
                (employee.login_time ? "Present" : "Absent");

              return (

                <View
                  key={employee.employee_id}
                >

                  <View style={styles.row}>

                    <View style={styles.left}>

                      <Avatar
                        name={employee.name}
                        size={46}
                      />

                      <View style={styles.info}>

                        <Text style={styles.name}>
                          {employee.name}
                        </Text>

                        <Text style={styles.id}>
                          {employee.employee_id}
                        </Text>

                      </View>

                    </View>

                    <View style={styles.right}>

                      <StatusChip
                        status={status}
                      />

                      <Text style={styles.time}>

                        {employee.login_time
                          ? employee.login_time.slice(0,5)
                          : "--:--"}

                        {employee.logout_time
                          ? ` • ${employee.logout_time.slice(0,5)}`
                          : ""}

                      </Text>

                    </View>

                  </View>

                  {

                    index !== rows.length - 1 &&

                    <Divider />

                  }

                </View>

              );

            })

          )

        }

      </AppCard>

    </View>

  );

}

const styles = StyleSheet.create({

  container:{

    marginTop:26,

  },

  card:{

    paddingVertical:8,

    paddingHorizontal:18,

  },

  row:{

    flexDirection:"row",

    justifyContent:"space-between",

    alignItems:"center",

    paddingVertical:14,

  },

  left:{

    flexDirection:"row",

    alignItems:"center",

    flex:1,

  },

  info:{

    marginLeft:14,

    flex:1,

  },

  name:{

    fontSize:13,

    fontWeight:"700",

    color:"#0F172A",

  },

  id:{

    marginTop:3,

    fontSize:12,

    color:"#94A3B8",

  },

  right:{

    alignItems:"flex-end",

    minWidth:105,

  },

  time:{

    marginTop:6,

    fontSize:11,

    color:"#64748B",

    fontWeight:"600",

  },

});